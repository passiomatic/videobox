from threading import Thread, Event
import time
from datetime import datetime
from dataclasses import dataclass
from functools import partial
import libtorrent as lt
from kivy.clock import Clock
from kivy.logger import Logger
import videobox.model as model
import videobox.utilities as utilities

MSG_TORRENT_ADD = "torrent.add"
MSG_TORRENT_UPDATE = "torrent.update"
MSG_TORRENT_DONE = "torrent.done"

TORRENT_USER_AGENT = "uTorrent/3.5.5(45271)"

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
    max_download_rate=1024 * 512,  # 0 means unconstrained
    max_upload_rate=1024 * 256,  # 0 means unconstrained
    proxy_host='',
    save_dir='.',
    add_callback=None,
    update_callback=None,
    done_callback=None,
)

# See https://www.libtorrent.org/reference-Alerts.html#alert_category_t
ALERT_MASK_STORAGE = lt.alert.category_t.storage_notification
ALERT_MASK_STATUS = lt.alert.category_t.status_notification
ALERT_MASK_PROGRESS = lt.alert.category_t.progress_notification
ALERT_MASK_ERROR = lt.alert.category_t.error_notification
ALERT_MASK_STATS = lt.alert.category_t.stats_notification
ALERT_MASK_ALL = lt.alert.category_t.all_categories

STATE_LABELS = {
    # Torrent has not started its download yet, and is currently checking existing files
    lt.torrent_status.states.checking_files: "Checking files",
    # Torrent is trying to download metadata from peers
    lt.torrent_status.states.downloading_metadata: "Fetching metadata",
    # The torrent is being downloaded
    lt.torrent_status.states.downloading: "Downloading",
    # Torrent has finished downloading but still doesn't have the entire torrent. i.e. some pieces are filtered and won't get downloaded
    lt.torrent_status.states.finished: "Finished",
    # Torrent has finished downloading and is a pure seeder
    lt.torrent_status.states.seeding: "Seeding",
    # The torrent is currently checking the fast resume data and comparing it to the files on disk
    lt.torrent_status.states.checking_resume_data: "Checking resume data",
}


@dataclass
class TorrentStatus:
    """
    Nicely formatted values for view presentation
    """
    handle: lt.torrent_handle  # Torrent's handle
    name: str  # Torrent's name
    size: int  # Bytes
    state: lt.torrent_status.state
    progress: int  # Percent downloaded
    download_speed: float  # KB/s
    upload_speed: float  # KB/s
    # total_download: float # MB
    seeds_count: int
    peers_count: int
    added_time: datetime
    # completed_time: datetime  # None if not completed yet
    info_hash: str

    @staticmethod
    def make(status):
        # if status.completed_time:
        #     completed_time = datetime.fromtimestamp(
        #         int(status.completed_time))
        # else:
        #     # Not completed yet
        #     completed_time = None
        return TorrentStatus(
            handle=status.handle,
            name=status.name,
            size=status.total,  # @@FIXME Is zero when seeding
            state=status.state,
            progress=int(status.progress * 100),
            download_speed=status.download_payload_rate // 1024,
            upload_speed=status.upload_payload_rate // 1024,
            # total_download = status.total_done // 1048576,
            seeds_count=status.num_seeds,
            peers_count=status.num_peers,
            added_time=datetime.fromtimestamp(int(status.added_time)),
            # completed_time=completed_time,
            info_hash=status.info_hashes.get_best()
        )

    def get_files(self):
        torrrent_file = self.handle.torrent_file()
        # @@TODO Maybe check torrent_status.has_metadata ?
        if torrrent_file:
            file_storage = torrrent_file.files()
            return [(file_storage.file_path(i), file_storage.file_size(i))
                    for i in range(file_storage.num_files())]
        else:
            raise TorrentClientError(
                f"Torrent {self.handle} has no metatada yet")

    @property
    def state_label(self):
        label = ""
        try:
            label = STATE_LABELS[self.state]
        except KeyError:
            pass
        return label

    @property
    def stats(self):
        return f"{self.state_label} • {self.progress}% of {utilities.format_size(self.size)} DL {self.download_speed}KB/s UP {self.upload_speed}KB/s from {self.peers_count} peers"

    def __str__(self):
        return self.stats


class TorrentClient(Thread):
    """
    Implements a simple torrent client
    """

    def __init__(self, client_options=None):
        super().__init__(name="TorrentClient worker")
        self.keep_running = True

        self._torrents_pool = {}

        options = DEFAULT_OPTIONS
        if client_options:
            options = DEFAULT_OPTIONS | client_options

        self.add_callback = options['add_callback']
        self.update_callback = options['update_callback']
        self.done_callback = options['done_callback']
        # self.store_data_callback = options['done_callback']
        self.save_dir = options['save_dir']

        # alert_mask = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS | ALERT_MASK_STATUS
        alert_mask = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS

        session_params = {
            'user_agent': TORRENT_USER_AGENT,
            'listen_interfaces': '%s:%d' % (options['listen_interface'], options['port']),
            'download_rate_limit': int(options['max_download_rate']),
            'upload_rate_limit': int(options['max_upload_rate']),
            'alert_mask': alert_mask,
            'outgoing_interfaces': options['outgoing_interface'],
            # 256 blocks, reduce 'have_piece' messages to give false positives
            'cache_size': 4096 // 16,
            'connections_limit': 200,  # Default
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

        Logger.info("App: Start TorrentClient thread")
        self.start()

    def load_torrents(self):
        """
        Add back previously saved torrents metadata
        """
        for transfer in model.get_incomplete_torrents():
            # params = lt.add_torrent_params()
            params = lt.read_resume_data(transfer.resume_data)
            self.session.async_add_torrent(params)

    def run(self):
        # Continue to check torrent events
        while self.keep_running:
            # @@TODO Wait up to half a second to check again for alerts
            # self.session.wait_for_alert(500)
            alerts = self.session.pop_alerts()
            for a in alerts:
                # alerts_log.append(a.message())

                # Add new torrent to list of torrent_status
                # if a.category() & lt.alert.category_t.status_notification:
                if isinstance(a, lt.add_torrent_alert):
                    h = a.handle
                    h.set_max_connections(MAX_CONNECTIONS_PER_TORRENT)
                    # h.set_max_uploads(-1)
                    self._torrents_pool[h] = h.status()
                    # Logger.debug(f"App: Added torrent {h} to pool")
                    if self.add_callback:
                        Clock.schedule_once(
                            partial(self.add_callback, TorrentStatus.make(h.status())))

                # Update torrent_status array for torrents that have changed some of their state
                elif isinstance(a, lt.state_update_alert):
                    for status in a.status:
                        old_status = self._torrents_pool[status.handle]
                        self._torrents_pool[status.handle] = status
                        if status.has_metadata != old_status.has_metadata:
                            # Got metadata since last update, save it
                            status.handle.save_resume_data()
                        if status.is_finished != old_status.is_finished:
                            # The is_finished flag changed, torrent has been downloaded
                            self.on_torrent_done(status.handle)
                            handle.pause()
                            Clock.schedule_once(
                                partial(self.done_callback, TorrentStatus.make(status)))
                        elif self.update_callback:
                            Clock.schedule_once(
                                partial(self.update_callback, TorrentStatus.make(status)))

                # Save Torrent data to resume faster later
                elif isinstance(a, lt.save_resume_data_alert):
                    data = lt.write_resume_data_buf(a.params)
                    handle = a.handle
                    # Sanity check
                    if handle in self._torrents_pool:
                        self.on_torrent_resume_data(handle, data)

            # for a in alerts_log:
            #     Logger.debug(a)
            # alerts_log.clear()

            # Ask for torrent status updates only if there's something to transfer
            if self._torrents_pool:
                self.session.post_torrent_updates()

            # Wait a bit and check again
            time.sleep(0.75)

        self.pause()
        Logger.info("App: Stopped TorrentClient thread")

    def on_torrent_resume_data(self, handle, resume_data):
        info_hash = str(handle.info_hash())
        try:
            torrent = model.get_torrent_for_release(info_hash)
            torrent.resume_data = resume_data
            torrent.state = model.TORRENT_GOT_METADATA
            torrent.last_updated_on = datetime.now()
            torrent.save()
        except model.Torrent.DoesNotExist as ex:
            Logger.warning(f"App: Could not save torrent {info_hash} metadata")

    def on_torrent_done(self, handle):
        info_hash = str(handle.info_hash())
        try:
            torrent = model.get_torrent_for_release(info_hash)
            torrent.state = model.TORRENT_DOWNLOADED
            torrent.last_updated_on = datetime.now()
            torrent.save()
        except model.Torrent.DoesNotExist as ex:
            Logger.warning(f"App: Could not update torrent {info_hash} status")

    def add_torrent(self, magnet_uri):
        params = lt.parse_magnet_uri(magnet_uri)
        params.save_path = self.save_dir
        # params.storage_mode = lt.storage_mode_t.storage_mode_sparse # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t
        params.flags |= lt.torrent_flags.duplicate_is_error & ~lt.torrent_flags.auto_managed
        self.session.async_add_torrent(params)

    def get_torrent_status(self, torrent_handle):
        if torrent_handle.is_valid():  # @@FIXME Or use torrent_handle.in_session()?
            torrent_status = torrent_handle.status()
            return TorrentStatus.make(torrent_status)
        else:
            raise TorrentClientError(
                f"Invalid torrent handle {torrent_handle}")

    # def remove_torrent(self, info_hash, delete_files=False):
    #     """
    #     Remove a torrent from download

    #     :param info_hash: str
    #     :param delete_files: bool
    #     :return:
    #     """
    #     try:
    #         torrent_handle = self._torrents_pool[info_hash]
    #         del self._torrents_pool[info_hash]
    #         self.session.remove_torrent(torrent_handle, delete_files)
    #     except KeyError:
    #         raise TorrentClientError(f'Invalid torrent hash {info_hash}')

    @property
    def torrents_status(self):
        return [self.get_torrent_status(handle) for handle in self._torrents_pool]

    def pause_torrent(self, handle, graceful_pause=1):
        handle.save_resume_data()
        handle.pause(graceful_pause)

    def pause(self, graceful_pause=1):
        for handle in self._torrents_pool:
            self.pause_torrent(handle, graceful_pause)
        self.session.pause()


class TorrentClientError(Exception):
    pass
