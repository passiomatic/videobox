from threading import Thread, Event
import time
from datetime import datetime, timezone
from dataclasses import dataclass
import jinja2.filters as filters
from flask import current_app
import libtorrent as lt
import videobox.models as models

TORRENT_USER_AGENT = "uTorrent/3.5.5(45271)"

MAX_CONNECTIONS = 200 # Default
MAX_CONNECTIONS_PER_TORRENT = 60

DHT_ROUTERS = [
    ('router.bittorrent.com', 6881),
    ('dht.transmissionbt.com', 6881),
    ('router.utorrent.com', 6881),
    ('dht.aelitis.com', 6881),
]

USER_AGENT = ("uTorrent", 3, 5, 5, 45271)

def default_add_callback(status):
    pass

def default_update_callback(status):
    pass

def default_done_callback(status):
    pass

DEFAULT_OPTIONS = dict(
    port=6881,
    listen_interface='0.0.0.0',
    outgoing_interface='',
    max_download_rate=256 * 1024,  # 0 means unconstrained
    max_upload_rate=256 * 128,  # 0 means unconstrained
    proxy_host='',
    save_dir='.',
    add_callback=default_add_callback,
    update_callback=default_update_callback,
    done_callback=default_done_callback,
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
    # Torrent is being downloaded
    lt.torrent_status.states.downloading: "Downloading",
    # Torrent has finished downloading but still doesn't have the entire torrent. 
    #  i.e. some pieces are filtered and won't get downloaded
    lt.torrent_status.states.finished: "Finished",
    # Torrent has finished downloading and is a pure seeder
    lt.torrent_status.states.seeding: "Seeding",
    # The torrent is currently checking the fast resume data and comparing it to the files on disk
    lt.torrent_status.states.checking_resume_data: "Checking resume data",
}

torrent_worker = None

class Torrent(object):
    """
    A higher-level torrent class for presentation layer
    """
    def __init__(self, torrent_status):
        self.handle=torrent_status.handle
        self.info_hash=str(torrent_status.info_hashes.get_best()).upper()
        self.name=torrent_status.name
        self.status=torrent_status.state
        self.progress=int(torrent_status.progress * 100)
        self.download_speed=torrent_status.download_payload_rate
        self.upload_speed=torrent_status.upload_payload_rate
        self.seeders_count=torrent_status.num_seeds
        self.peers_count=torrent_status.num_peers

    @property
    def status_label(self):
        label = "—"
        try:
            label = STATE_LABELS[self.status]
        except KeyError:
            pass
        return label

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
    def stats(self):
        if self.status == lt.torrent_status.states.seeding:
            return f"{self.status_label} at {filters.do_filesizeformat(self.upload_speed)}/s to {self.peers_count} peers"
        else:
            return f"{self.status_label} ({self.progress}% complete) • DL {filters.do_filesizeformat(self.download_speed)}/s UP {filters.do_filesizeformat(self.upload_speed)}/s from {self.peers_count} peers"
        
    def __str__(self):
        return f'{self.name} ({self.status_label})'



class TorrentClient(Thread):
    """
    Simple torrent client
    """

    def __init__(self, client_options=None):
        super().__init__(name="TorrentClient worker")
        self.app = current_app._get_current_object()
        self.abort_event = Event()        
        
        self._torrents_pool = {}

        options = DEFAULT_OPTIONS
        if client_options:
            options = DEFAULT_OPTIONS | client_options
        
        self.save_dir = options['save_dir']

        self.add_callback = options['add_callback']
        self.update_callback = options['update_callback']
        self.done_callback = options['done_callback']

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
            'connections_limit': MAX_CONNECTIONS,
            'peer_fingerprint': lt.generate_fingerprint('UT', 3, 5, 5, 45271),
            'share_ratio_limit': 100, # The amounth of seeded is the same as download
            'seed_time_ratio_limit': 200, # Double the time as downloader 
            'seed_time_limit': 60 * 60, # Seconds

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

    def abort(self):
        self.abort_event.set()

    def resume_torrents(self):
        """
        Add back to session incomplete torrents
        """
        for transfer in models.get_incomplete_torrents():
            # params = lt.add_torrent_params()
            params = lt.read_resume_data(transfer.resume_data)
            self.session.async_add_torrent(params)

    def run(self):
        # Keep checking for torrent events
        while not self.abort_event.is_set():
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
                    #self.app.logger.debug(f"added torrent {h} to pool")
                    self.add_callback(Torrent(h.status()))

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
                            # status.handle.pause()
                            self.done_callback(Torrent(status))
                        else:
                            self.update_callback(Torrent(status))

                # Save Torrent data to resume faster later
                elif isinstance(a, lt.save_resume_data_alert):
                    data = lt.write_resume_data_buf(a.params)
                    handle = a.handle
                    # Sanity check
                    if handle in self._torrents_pool:
                        self.on_torrent_resume_data(handle, data)

            # Ask for torrent status updates only if there's something to transfer
            if self._torrents_pool:
                self.session.post_torrent_updates()

            # Wait a bit and check again
            time.sleep(0.75)

        self.pause()
        self.app.logger.debug(f"Stopped {self.name} #{id(self)} thread")

    def on_torrent_resume_data(self, handle, resume_data):
        self._update_torrent(handle, models.TORRENT_GOT_METADATA, resume_data)

    def on_torrent_done(self, handle):
        self._update_torrent(handle, models.TORRENT_DOWNLOADED)

    def _update_torrent(self, handle, status, resume_data=None):
        info_hash = str(handle.info_hash())
        torrent = models.get_torrent_for_release(info_hash)
        if torrent:
            if resume_data:
                torrent.resume_data = resume_data
            torrent.status = status
            torrent.save()
        else:
            self.app.logger.warning(f"Could not update torrent {info_hash} to {status}")

    def add_torrent(self, release):
        models.add_torrent(release)
        params = lt.parse_magnet_uri(release.magnet_uri)
        params.save_path = self.save_dir
        # params.storage_mode = lt.storage_mode_t.storage_mode_sparse # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t
        #params.flags |= (lt.torrent_flags.duplicate_is_error & ~lt.torrent_flags.auto_managed)
        params.flags |= lt.torrent_flags.duplicate_is_error
        self.session.async_add_torrent(params)

    def get_torrent(self, handle):
        if handle.is_valid():  # @@FIXME Or use handle.in_session()?
            torrent_status = handle.status()
            return Torrent(torrent_status)
        else:
            raise TorrentClientError(
                f"Invalid torrent handle {handle.id}")

    # def remove_torrent(self, info_hash, delete_files=False):
    #     try:
    #         torrent_handle = self._torrents_pool[info_hash]
    #         del self._torrents_pool[info_hash]
    #         self.session.remove_torrent(torrent_handle, delete_files)
    #     except KeyError:
    #         raise TorrentClientError(f'Invalid torrent hash {info_hash}')

    @property
    def torrents(self):
        return [self.get_torrent(handle) for handle in self._torrents_pool]

    def pause_torrent(self, handle, graceful_pause=True):
        handle.save_resume_data()
        handle.pause(1 if graceful_pause else 0)

    def pause(self, graceful_pause=True):
        for handle in self._torrents_pool:
            self.pause_torrent(handle, graceful_pause)
        self.session.pause()


class TorrentClientError(Exception):
    pass
