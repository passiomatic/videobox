from threading import Thread
from datetime import datetime
import logging
import libtorrent as lt
import time
from dataclasses import dataclass
import wx 
import views.theme 

MAX_CONNECTIONS_PER_TORRENT = 60

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
    max_download_rate= 1024 * 1024,  # 0 means unconstrained
    max_upload_rate= 1024 * 512,  # 0 means Uunconstrained
    proxy_host='',
    save_dir='' #@@TODO Use this instead of add_torrent(save_path...)
)

# See https://www.libtorrent.org/reference-Alerts.html#alert_category_t
ALERT_MASK_STORAGE = lt.alert.category_t.storage_notification
ALERT_MASK_STATUS = lt.alert.category_t.status_notification
ALERT_MASK_PROGRESS = lt.alert.category_t.progress_notification
ALERT_MASK_ERROR = lt.alert.category_t.error_notification
ALERT_MASK_STATS = lt.alert.category_t.stats_notification
ALERT_MASK_ALL = lt.alert.category_t.all_categories

@dataclass
class TorrentStatus:
    """
    Nicely formatted values for view presentation
    """
    handle: lt.torrent_handle # Torrent's name
    name: str # Torrent's name
    size: int # Bytes
    state: lt.torrent_status.state # Torrent's current state (downloading, seeding, etc.)
    progress: int # Percent downloaded 
    download_speed: float # KB/s
    upload_speed: float # KB/s
    # total_download: float # MB
    # total_upload: float # MB
    seeds_count: int
    peers_count: int
    added_time: datetime 
    completed_time: datetime # None if not completed yet
    #info_hash: str

    @staticmethod
    def make(status):
        if status.completed_time:
            completed_time = datetime.fromtimestamp(
                int(status.completed_time))
        else:
            # Not completed yet
            completed_time = None        
        return TorrentStatus(
            handle = status.handle,
            name = status.name,
            size = status.total,
            state= status.state,
            progress = int(status.progress * 100),
            download_speed = status.download_payload_rate // 1024,
            upload_speed = status.upload_payload_rate // 1024,
            # total_download = status.total_done // 1048576,
            # total_upload = status.total_payload_upload // 1048576,
            seeds_count = status.num_seeds,
            peers_count = status.num_peers,
            added_time = datetime.fromtimestamp(int(status.added_time)),
            completed_time = completed_time
            #'info_hash': info_hash,
            )        

    def __str__(self):
        return f"{self.progress}% of {views.theme.format_size(self.size)}. DL {self.download_speed}KB/s / UP {self.upload_speed}KB/s from {self.peers_count} peers"

class Torrenter(Thread):
    """
    Implements a simple torrent client
    """

    def __init__(self, client_options=None, update_callback=None):
        super().__init__(name="Torrenter worker")
        self.update_callback = update_callback

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
            'connections_limit': 200, # Default
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
                #alerts_log.append(a.message())

                # Add new torrent to list of torrent_status
                #if a.category() & lt.alert.category_t.status_notification:
                if isinstance(a, lt.add_torrent_alert):
                    h = a.handle
                    h.set_max_connections(MAX_CONNECTIONS_PER_TORRENT)
                    h.set_max_uploads(-1)
                    self.torrents_pool[h] = h.status()                    
                    logging.info(f"Added torrent {h} to pool")                    
                    if self.update_callback:
                        wx.CallAfter(self.update_callback, h)
                    
                # Update torrent_status array for torrents that have changed some of their state
                if isinstance(a, lt.state_update_alert):
                    for s in a.status:
                        self.torrents_pool[s.handle] = s
                        logging.debug(f"Got status update for torrent {s.handle}")
                        if self.update_callback:
                            wx.CallAfter(self.update_callback, s.handle)

            # for a in alerts_log:
            #     logging.debug(a)
            #alerts_log.clear()

            # Ask for torrent status updates only if there's something to transfer
            if self.torrents_pool:
                self.session.post_torrent_updates()

            # Wait a bit and check again
            time.sleep(0.75)

        logging.info("Stopped torrenter thread")
        self.session.pause()

    def add_torrent(self, save_path, magnet_uri):
        params = lt.parse_magnet_uri(magnet_uri)
        params.save_path = save_path
        # params.storage_mode = lt.storage_mode_t.storage_mode_sparse # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t
        params.flags |= lt.torrent_flags.duplicate_is_error | lt.torrent_flags.auto_managed
        self.session.async_add_torrent(params)

    def get_torrent_status(self, torrent_handle):
        # try:
        #     torrent_status = self.torrents_pool[handle]
        # except KeyError:
        #     raise TorrenterError(f'Torrent handle {handle} not found in pool')
        
        if torrent_handle.is_valid(): ##@@FIXME Or use torrent_handle.in_session()? 
            torrent_status = torrent_handle.status()
            return TorrentStatus.make(torrent_status)
        else:
            raise TorrenterError(f"Invalid torrent handle {torrent_handle}")
            

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

    # def get_torrent_info(self, handle):
    #     """
    #     Get torrent info in a human-readable format
    #     """
    #     torrent_status = self.get_torrent_status(handle)
    #     if torrent_status.completed_time:
    #         completed_time = datetime.fromtimestamp(
    #             int(torrent_status.completed_time))
    #     else:
    #         # None if not completed yet
    #         completed_time = None
    #     return {'name': torrent_status.name,
    #             #'size': torr_info.total_size(),
    #             'state': torrent_status.state,
    #             'progress': int(torrent_status.progress * 100),
    #             'dl_speed': int(torrent_status.download_payload_rate / 1024),
    #             'ul_speed': int(torrent_status.upload_payload_rate / 1024),
    #             'total_download': int(torrent_status.total_done / 1048576),
    #             'total_upload': int(torrent_status.total_payload_upload / 1048576),
    #             'num_seeds': torrent_status.num_seeds,
    #             'num_peers': torrent_status.num_peers,
    #             'added_time': datetime.fromtimestamp(int(torrent_status.added_time)),
    #             'completed_time': completed_time,
    #             #'info_hash': info_hash,
    #             }

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
