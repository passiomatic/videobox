from threading import Thread
from datetime import datetime
import logging
from unicodedata import category
import libtorrent as lt
import time

DHT_ROUTERS = [
    ('router.bittorrent.com', 6881),
    ('dht.transmissionbt.com', 6881),
    ('router.utorrent.com', 6881),
    ('dht.aelitis.com', 6881),
]

USER_AGENT = ("uTorrent", 3, 5, 5, 45271)

DEFAULT_OPTIONS = dict(
    port=6881,
    listen_interface='0.0.0.0',
    outgoing_interface='',
    max_download_rate=-1,  # Unconstrained
    max_upload_rate=-1,  # Unconstrained
    proxy_host=''
)

# See https://www.libtorrent.org/reference-Alerts.html#alert_category_t
ALERT_MASK_STORAGE = lt.alert.category_t.storage_notification
ALERT_MASK_STATUS = lt.alert.category_t.status_notification
ALERT_MASK_PROGRESS = lt.alert.category_t.progress_notification
ALERT_MASK_ERROR = lt.alert.category_t.error_notification
ALERT_MASK_STATS = lt.alert.category_t.stats_notification
ALERT_MASK_ALL = lt.alert.category_t.all_categories


class Torrenter(Thread):
    """
    Implements a simple torrent client
    """

    def __init__(self, client_options=None):
        super().__init__(name="Torrenter worker")

        # Map info hashes to current Torrent handlers
        self.torrents_pool = {}

        options = DEFAULT_OPTIONS
        if client_options:
            options = DEFAULT_OPTIONS | client_options

        #alert_mask = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS | ALERT_MASK_STATUS
        alert_mask = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS

        session_params = {
            # 'user_agent': 'Videobox/{0}.{1}.{2}'.format(*configuration.VERSION),
            'user_agent': 'uTorrent/3.5.5(45271)',
            'listen_interfaces': '%s:%d' % (options['listen_interface'], options['port']),
            'download_rate_limit': int(options['max_download_rate']),
            'upload_rate_limit': int(options['max_upload_rate']),
            'alert_mask': alert_mask,
            'outgoing_interfaces': options['outgoing_interface'],
            # 256 blocks, reduce 'have_piece' messages to give false positives
            'cache_size': 4096 // 16,
            'peer_fingerprint': lt.generate_fingerprint('UT', 3, 5, 5, 45271)
        }

        # if options.proxy_host != '':
        #     session_params['proxy_hostname'] = options.proxy_host.split(':')[0]
        #     session_params['proxy_type'] = lt.proxy_type_t.http
        #     session_params['proxy_port'] = options.proxy_host.split(':')[1]

        self.session = lt.session(session_params)

        for router, port in DHT_ROUTERS:
            self.session.add_dht_router(router, port)

        self.session.start_dht()
        self.session.start_lsd()
        self.session.start_upnp()
        self.session.start_natpmp()

        logging.info("Start torrenter thread")
        self.start()

    def run(self):
        # Continue to check torrent events
        alerts_log = []
        alive = True
        while alive:
            # @@TODO Wait up to half a second to check again for alerts
            #self.session.wait_for_alert(500)
            alerts = self.session.pop_alerts()
            for a in alerts:
                alerts_log.append(a.message())

                # Add new torrent to list of torrent_status
                if isinstance(a, lt.add_torrent_alert):
                    h = a.handle
                    h.set_max_connections(60)
                    h.set_max_uploads(-1)
                    self.torrents_pool[h] = h.status()
                    logging.info(f"Added torrent {h} to pool")

                # Update torrent_status array for torrents that have changed some of their state
                if isinstance(a, lt.state_update_alert):
                    for s in a.status:
                        self.torrents_pool[s.handle] = s
                        logging.debug(f"Got status update for torrent {s.handle}")

            for a in alerts_log:
                logging.debug(a)

            # Ask for torrent_status updates only if there's something downloading
            #if self.torrents_pool:
            self.session.post_torrent_updates()

            # Wait for half a second and check again
            time.sleep(0.5)

        logging.info("Stopped torrenter thread")
        self.session.pause()

    def add_torrent(self, save_path, magnet_uri):
        params = lt.parse_magnet_uri(magnet_uri)
        params.save_path = save_path
        # atp.storage_mode = lt.storage_mode_t.storage_mode_sparse # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t
        params.flags |= lt.torrent_flags.duplicate_is_error | lt.torrent_flags.auto_managed
        self.session.async_add_torrent(params)

    def get_torrent_status(self, info_hash):
        try:
            torrent_handle = self.torrents_pool[info_hash]
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')
        if torrent_handle.is_valid():
            return torrent_handle.status()
        return None

    # def _get_torrent_info(self, info_hash):
    #     try:
    #         torrent_handle = self._torrents_pool[info_hash]
    #     except KeyError:
    #         raise TorrenterError(f'Invalid torrent hash {info_hash}')
    #     if torrent_handle.is_valid():
    #         return torrent_handle.get_torrent_info()
    #     return None

    def remove_torrent(self, info_hash, delete_files=False):
        """
        Remove a torrent from download

        :param info_hash: str
        :param delete_files: bool
        :return:
        """
        try:
            torrent_handle = self.torrents_pool[info_hash]
            del self.torrents_pool[info_hash]
            self.session.remove_torrent(torrent_handle, delete_files)
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')

    def pause_torrent(self, info_hash, graceful_pause=1):
        try:
            self.torrents_pool[info_hash].pause(graceful_pause)
        except KeyError:
            raise TorrenterError(f'Invalid torrent hash {info_hash}')

    def resume_torrent(self, info_hash):
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
            completed_time = datetime.fromtimestamp(
                int(torr_status.completed_time))
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
        listing = []
        for info_hash in self.torrents_pool:
            torrent_info = self.get_torrent_info(info_hash)
            if torrent_info is not None:
                listing.append(torrent_info)
        return listing

    def pause_all(self, graceful_pause=1):
        for info_hash in self.torrents_pool:
            self.pause_torrent(info_hash, graceful_pause)

    def resume_all(self):
        for info_hash in self.torrents_pool:
            self.resume_torrent(info_hash)

    # def get_files(self, info_hash):
    #     """
    #     Get the list of videofiles in a torrent

    #     :param info_hash:
    #     :return: a list of tuples (path, size)
    #     """
    #     file_storage = self._get_torrent_info(info_hash).files()
    #     # if libtorrent.version < '1.1.0':
    #     #     return [(file_.path.decode('utf-8'), file_.size) for file_ in file_storage]
    #     # else:
    #     return [(file_storage.file_path(i), file_storage.file_size(i))
    #             for i in range(file_storage.num_files())]

    # @property
    # def is_torrent_added(self):
    #     """Torrent added flag"""
    #     return self._torrent_added.is_set()

    # @property
    # def last_added_torrent(self):
    #     """The last added torrent info"""
    #     return self._last_added_torrent.contents

class TorrenterError(Exception):
    pass
