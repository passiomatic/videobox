"""
The module implements a torrent client downloading contents on separate threads.

This is adapted from Roman Miroshnychenko's Yet Anoter Torrent Player
https://github.com/romanvm/kodi.yatp

Most of the work done was to update it to libtorrent 2.x.x.
"""

from __future__ import division
import os
import threading
from datetime import datetime
import pickle
#from contextlib import closing
import logging
import libtorrent as lt
import time
import configuration 

DHT_ROUTERS = [
    ('router.bittorrent.com', 6881),
    ('dht.transmissionbt.com', 6881),
    ('router.utorrent.com', 6881),
    ('dht.aelitis.com', 6881),
]

class TorrenterError(Exception):
    pass


class Buffer(object):
    """Thread-safe data buffer"""

    def __init__(self, contents=None):
        self._lock = threading.RLock()
        self._contents = contents

    @property
    def contents(self):
        """Get buffer contents"""
        with self._lock:
            return self._contents

    @contents.setter
    def contents(self, value):
        """Set buffer contents"""
        with self._lock:
            self._contents = value

USER_AGENT = ("uTorrent", 3, 5, 5, 45271)

class Torrenter(object):
    """
    Implements a simple torrent client
    """

    def __init__(self, start_port=6881, end_port=6891):
        """
        """
        # torrents_pool is used to map torrent handles to their sha1 info_hashes (string hex digests)
        # Item format {info_hashes: torrent_handle}
        self._torrents_pool = {}
        # Worker threads
        self._add_torrent_thread = None
        # Signal events
        self._torrent_added = threading.Event()
        # Inter-thread data buffer.
        self._last_added_torrent = Buffer()

        options = dict(
            port=6881,
            listen_interface='0.0.0.0',
            outgoing_interface='',
            max_download_rate=-1, # Unconstrained
            max_upload_rate=-1, # Unconstrained
            proxy_host=''
        )
        #self.options = options

        # Ports
        # if options.port < 0 or options.port > 65525:
        #     options.port = 6881

        # Lower cache size is needed for libtorrent to dump data on disk more often,
        # otherwise have_piece may give false positives for pieces
        # that are in the memory cache but not saved to disk yet.

        settings = {
            #'user_agent': 'Videobox/{0}.{1}.{2}'.format(*configuration.VERSION),
            'user_agent': 'uTorrent/3.5.5(45271)',
            'listen_interfaces': '%s:%d' % (options['listen_interface'], options['port']),
            'download_rate_limit': int(options['max_download_rate']),
            'upload_rate_limit': int(options['max_upload_rate']),
            'alert_mask': lt.alert.category_t.all_categories,
            'outgoing_interfaces': options['outgoing_interface'],
            'cache_size': 4096 // 16, # 256 blocksù
            'peer_fingerprint': lt.generate_fingerprint('UT', 3, 5, 5, 45271)
        }
        
        # if options.proxy_host != '':
        #     settings['proxy_hostname'] = options.proxy_host.split(':')[0]
        #     settings['proxy_type'] = lt.proxy_type_t.http
        #     settings['proxy_port'] = options.proxy_host.split(':')[1]

        # Init session
        self._session = lt.session(settings)

        for router, port in DHT_ROUTERS:
            self._session.add_dht_router(router, port)

        self._session.start_dht()
        self._session.start_lsd()
        self._session.start_upnp()
        self._session.start_natpmp()

    # def set_encryption_policy(self, enc_policy=1):
    #     """
    #     Set encryption policy for the session

    #     :param enc_policy: int - 0 = forced, 1 = enabled, 2 = disabled
    #     :return:
    #     """
    #     pe_settings = self._session.get_pe_settings()
    #     pe_settings.in_enc_policy = pe_settings.out_enc_policy = lt.enc_policy(
    #         enc_policy)
    #     self._session.set_pe_settings(pe_settings)

    # def set_session_settings(self, **settings):
    #     """
    #     Set session settings.

    #     See `libtorrent API docs`_ for more info.

    #     :param settings: session settings key=value pairs
    #     :return:

    #     .. _libtorrent API docs: http://web.archive.org/web/20190524062906/https://www.rasterbar.com/products/libtorrent/manual.html#session-customization
    #     """
    #     ses_settings = self._session.get_settings()
    #     for key, value in settings.items():
    #         ses_settings[key] = value
    #     self._session.set_settings(ses_settings)

    def add_torrent_new(self, save_path, magnet_uri):
        #atp = lt.add_torrent_params()
        atp = lt.parse_magnet_uri(magnet_uri)
        atp.save_path = save_path
        #atp.storage_mode = lt.storage_mode_t.storage_mode_sparse # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t
        atp.flags |= lt.torrent_flags.duplicate_is_error | lt.torrent_flags.auto_managed
        self._session.async_add_torrent(atp)

    def add_torrent_async(self, torrent, save_path, paused=False, cookies=None):
        """
        Add a torrent in a non-blocking way.

        This method will add a torrent in a separate thread. After calling the method,
        the caller should periodically check is_torrent_added flag and, when
        the flag is set, retrieve results from last_added_torrent.

        :param torrent: str - path to a .torrent file or a magnet link
        :param save_path: str - save path
        :param paused: bool
        :param cookies: dict
        :return:
        """
        self._add_torrent_thread = threading.Thread(target=self.add_torrent,
                                                    args=(torrent, save_path, paused, cookies))
        self._add_torrent_thread.daemon = True
        self._add_torrent_thread.start()

    def add_torrent(self, torrent, save_path, paused=False, cookies=None):
        """
        Add a torrent download

        :param torrent: str
        :param save_path: str
        :param paused: bool
        :param cookies: dict
        :return:
        """
        self._torrent_added.clear()
        torrent_handle = self._add_torrent(torrent, save_path, cookies=cookies)
        info_hash = str(torrent_handle.info_hash())
        self._last_added_torrent.contents = {
            'name': torrent_handle.name().decode('utf-8'),
            'info_hash': info_hash,
            'files': self.get_files(info_hash)
        }
        # The tested variant of pause management. Other options don't work with 1.x.x.
        # Do not change unless does not work as expected!
        if paused:
            self.pause_torrent(info_hash)
        else:
            self.resume_torrent(info_hash)
        self._torrent_added.set()

    def _add_torrent(self, torrent, save_path, resume_data=None, cookies=None):
        """
        Add a torrent to the pool.

        :param torrent: str - magnet link
        :param save_path: str - torrent save path
        :param resume_data: str - bencoded torrent resume data
        :return: object - torrent_handle
        """
        add_torrent_params = {'save_path': os.path.abspath(save_path),
                              'storage_mode': lt.storage_mode_t.storage_mode_sparse}
        if resume_data is not None:
            add_torrent_params['resume_data'] = resume_data
        if isinstance(torrent, dict):
            add_torrent_params['ti'] = lt.torrent_info(torrent)
        elif torrent[:7] == 'magnet:':
            if isinstance(torrent, str):
                # libtorrent doesn't like unicode objects here
                torrent = torrent.encode('utf-8')
            add_torrent_params['url'] = torrent
        else:
            raise TorrenterError(
                'Error when adding torrent: {0}'.format(torrent))
        torrent_handle = self._session.add_torrent(add_torrent_params)
        while not torrent_handle.has_metadata():  # Wait until torrent metadata are populated
            time.sleep(0.1)
        torrent_handle.auto_managed(False)
        self._torrents_pool[str(torrent_handle.info_hash())] = torrent_handle
        return torrent_handle

    def _get_torrent_status(self, info_hash):
        try:
            torrent_handle = self._torrents_pool[info_hash]
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')
        if torrent_handle.is_valid():
            return torrent_handle.status()
        return None

    def _get_torrent_info(self, info_hash):
        try:
            torrent_handle = self._torrents_pool[info_hash]
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')
        if torrent_handle.is_valid():
            return torrent_handle.get_torrent_info()
        return None

    def remove_torrent(self, info_hash, delete_files=False):
        """
        Remove a torrent from download

        :param info_hash: str
        :param delete_files: bool
        :return:
        """
        try:
            torrent_handle = self._torrents_pool[info_hash]
            del self._torrents_pool[info_hash]
            self._session.remove_torrent(torrent_handle, delete_files)
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')

    def pause_torrent(self, info_hash, graceful_pause=1):
        """
        Pause a torrent

        :param info_hash: str
        :param graceful_pause: int
        :return:
        """
        try:
            self._torrents_pool[info_hash].pause(graceful_pause)
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')

    def resume_torrent(self, info_hash):
        """
        Resume a torrent

        :param info_hash: str
        :return:
        """
        try:
            self._torrents_pool[info_hash].resume()
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')

    def get_torrent_info(self, info_hash):
        """
        Get torrent info in a human-readable format. The following info are returned:

            name - torrent's name
            size - MB
            state - torrent's current state
            dl_speed - KB/s
            ul_speed - KB/s
            total_download - MB
            total_upload - MB
            progress - int %
            num_peers
            num_seeds
            added_time - datetime object
            completed_time - see above or None if not completed yet
            info_hash - torrent's info_hash hexdigest in lowecase
        """
        torr_info = self._get_torrent_info(info_hash)
        torr_status = self._get_torrent_status(info_hash)
        if torr_info is None or torr_status is None:
            return None
        #state = torr_status.state
        # if torr_status.paused:
        #     state = 'paused'
        # elif state == 'finished':
        #     state = 'incomplete'        
        if torr_status.completed_time:            
            completed_time = datetime.fromtimestamp(int(torr_status.completed_time))
        else:
            # Zero if not completed yet
            completed_time = None
        return {'name': torr_info.name().decode('utf-8'),
                'size': int(torr_info.total_size() / 1048576),
                'state': torr_status.state,
                'progress': int(torr_status.progress * 100),
                'dl_speed': int(torr_status.download_payload_rate / 1024),
                'ul_speed': int(torr_status.upload_payload_rate / 1024),
                'total_download': int(torr_status.total_done / 1048576),
                'total_upload': int(torr_status.total_payload_upload / 1048576),
                'num_seeds': torr_status.num_seeds,
                'num_peers': torr_status.num_peers,
                'added_time': datetime.fromtimestamp(int(torr_status.added_time)),
                'completed_time': completed_time,
                'info_hash': info_hash,
                }

    def get_all_torrents_info(self):
        """
        Get info for all torrents in the session.

        Note that the torrents info list will have a random order.
        It is up to the caller to sort the list accordingly.
        """
        listing = []
        for info_hash in self._torrents_pool:
            torrent_info = self.get_torrent_info(info_hash)
            if torrent_info is not None:
                listing.append(torrent_info)
        return listing

    def pause_all(self, graceful_pause=1):
        """
        Pause all torrents

        :return:
        """
        for info_hash in self._torrents_pool.iterkeys():
            self.pause_torrent(info_hash, graceful_pause)

    def resume_all(self):
        """
        Resume all torrents

        :return:
        """
        for info_hash in self._torrents_pool.iterkeys():
            self.resume_torrent(info_hash)

    # def prioritize_file(self, info_hash, file_index, priority):
    #     """
    #     Prioritize a file in a torrent

    #     If all piece priorities in the torrent are set to 0, to enable downloading an individual file
    #     priority value must be no less than 2.

    #     :param info_hash: str - torrent info-hash
    #     :param file_index: int - the index of a file in the torrent
    #     :param priority: int - priority from 0 to 7.
    #     :return:
    #     """
    #     self._torrents_pool[info_hash].file_priority(file_index, priority)

    # def set_piece_priorities(self, info_hash, priority=1):
    #     """
    #     Set priorities for all pieces in a torrent

    #     :param info_hash: str
    #     :param priority: int
    #     :return:
    #     """
    #     torrent_handle = self._torrents_pool[info_hash]
    #     [torrent_handle.piece_priority(piece, priority) for piece in xrange(
    #         torrent_handle.get_torrent_info().num_pieces())]

    def get_files(self, info_hash):
        """
        Get the list of videofiles in a torrent

        :param info_hash:
        :return: a list of tuples (path, size)
        """
        file_storage = self._get_torrent_info(info_hash).files()
        # if libtorrent.version < '1.1.0':
        #     return [(file_.path.decode('utf-8'), file_.size) for file_ in file_storage]
        # else:
        return [(file_storage.file_path(i), file_storage.file_size(i))
                for i in range(file_storage.num_files())]

    @property
    def is_torrent_added(self):
        """Torrent added flag"""
        return self._torrent_added.is_set()

    @property
    def last_added_torrent(self):
        """The last added torrent info"""
        return self._last_added_torrent.contents


class TorrenterPersistent(Torrenter):
    """
    TorrenterPersistent(start_port=6881, end_port=6891, persistent=False, resume_dir='')

    A persistent version of Torrenter

    It stores the session state and torrents data on disk

    :param start_port: int
    :param end_port: int
    :param persistent: bool - store persistent torrent data on disk
    :param resume_dir: str - the directory to store persistent torrent data
    """

    def __init__(self, start_port=6881, end_port=6891, persistent=False, resume_dir=''):
        """
        Class constructor

        :param start_port: int
        :param end_port: int
        :param persistent: bool - store persistent torrent data on disk
        :param resume_dir: str - the directory to store persistent torrent data
        :return:
        """
        super().__init__(start_port, end_port)
        # Use persistent storage for session and torrents info
        self._persistent = persistent
        # The directory where session and torrent data are stored
        self._resume_dir = os.path.abspath(resume_dir)
        if self._persistent:
            try:
                self._load_session_state()
            except TorrenterError:
                self._save_session_state()
            self._load_torrents()

    def add_torrent(self, torrent, save_path, paused=False, cookies=None):
        """
        Add a torrent download

        :param torrent: str
        :param save_path: str
        :param paused: bool
        :param cookies: dict
        :return:
        """
        super().add_torrent(
            torrent, save_path, paused, cookies)
        if self._persistent:
            self._save_torrent_info(
                self._torrents_pool[self._last_added_torrent.contents['info_hash']])

    def _save_session_state(self):
        """
        Save session state

        :return:
        """
        if self._persistent:
            with open(os.path.join(self._resume_dir, 'session.state'), mode='wb') as state_file:
                pickle.dump(self._session.save_state(), state_file)
        else:
            raise TorrenterError(
                'Trying to save the state of a non-persistent instance!')

    def _load_session_state(self):
        """
        Load session state

        :return:
        """
        try:
            with open(os.path.join(self._resume_dir, 'session.state'), mode='rb') as state_file:
                self._session.load_state(pickle.load(state_file))
        except IOError:
            raise TorrenterError('.state file not found!')

    def _save_resume_data(self, info_hash, force_save=False):
        """
        Save fast-resume data for a torrent.

        :param info_hash: str
        :return:
        """
        if self._persistent:
            torrent_handle = self._torrents_pool[info_hash]
            if torrent_handle.need_save_resume_data() or force_save:
                resume_data = lt.bencode(
                    torrent_handle.write_resume_data())
                with open(os.path.join(self._resume_dir, info_hash + '.resume'), mode='r+b') as meta_file:
                    metadata = pickle.load(meta_file)
                    metadata['resume_data'] = resume_data
                    meta_file.seek(0)
                    pickle.dump(metadata, meta_file)
                    meta_file.truncate()
        else:
            raise TorrenterError(
                'Trying to save torrent metadata for a non-persistent instance!')

    def save_all_resume_data(self, force_save=False):
        """
        Save fast-resume data for all torrents

        :return:
        """
        if self._persistent:
            for key in self._torrents_pool.iterkeys():
                self._save_resume_data(key, force_save)
            self._session.save_state()
        else:
            raise TorrenterError(
                'Trying to save torrent metadata for a non-persistent instance!')

    def _save_torrent_info(self, torrent_handle):
        """
        Save torrent metatata and a .torrent file for resume.

        :param torrent_handle: object - torrent handle
        :return:
        """
        if self._persistent:
            info_hash = str(torrent_handle.info_hash())
            torr_filepath = os.path.join(
                self._resume_dir, info_hash + '.torrent')
            meta_filepath = os.path.join(
                self._resume_dir, info_hash + '.resume')
            torr_info = torrent_handle.get_torrent_info()
            torr_file = lt.create_torrent(torr_info)
            torr_content = torr_file.generate()
            torr_bencoded = lt.bencode(torr_content)
            with open(torr_filepath, 'wb') as t_file:
                t_file.write(torr_bencoded)
            metadata = {'name': torrent_handle.name(),
                        'info_hash': info_hash,
                        'save_path': torrent_handle.save_path(),
                        'resume_data': None}
            with open(meta_filepath, mode='wb') as m_file:
                pickle.dump(metadata, m_file)
        else:
            raise TorrenterError(
                'Trying to save torrent metadata for a non-persistent instance!')

    def _load_torrent_info(self, filepath):
        """
        Load torrent state from a pickle file and add the torrent to the pool.

        :param filepath: str
        :return:
        """
        try:
            with open(filepath, mode='rb') as m_file:
                metadata = pickle.load(m_file)
        except (IOError, EOFError, ValueError, pickle.PickleError):
            addon.log_error(
                'Resume file "{0}" is missing or corrupted!'.format(filepath))
        else:
            torrent = os.path.join(
                self._resume_dir, metadata['info_hash'] + '.torrent')
            self._add_torrent(
                torrent, metadata['save_path'], metadata['resume_data'])

    def _load_torrents(self):
        """
        Load all torrents

        :return:
        """
        dir_listing = os.listdir(self._resume_dir)
        for item in dir_listing:
            if item[-7:] == '.resume':
                self._load_torrent_info(os.path.join(self._resume_dir, item))

    def remove_torrent(self, info_hash, delete_files=False):
        """
        Remove a torrent from download

        :param info_hash: str
        :param delete_files: bool
        :return:
        """
        super().remove_torrent(
            info_hash, delete_files)
        if self._persistent:
            try:
                os.remove(os.path.join(
                    self._resume_dir, info_hash + '.resume'))
                os.remove(os.path.join(
                    self._resume_dir, info_hash + '.torrent'))
            except OSError:
                raise TorrenterError('Info files not found!')
