from threading import Thread, Event
import time
from pathlib import Path
#from datetime import datetime, timezone
import jinja2.filters as filters
from flask import current_app
import libtorrent as lt
import videobox
import videobox.models as models

TORRENT_USER_AGENT = ("VB", *videobox.version_info)
TORRENT_USER_AGENT_STRING = f"Videobox/{videobox.__version__}"
TORRENT_DEFAULT_PORT = 6881
MAX_CONNECTIONS = 200
MAX_CONNECTIONS_PER_TORRENT = 60
SAVE_RESUME_DATA_INTERVAL = 90 # Seconds

DHT_ROUTERS = [
    ('router.bittorrent.com', 6881),
    ('dht.transmissionbt.com', 6881),
    ('router.utorrent.com', 6881),
    ('dht.aelitis.com', 6881),
]

def nop_callback(status):
    pass

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
        self.info_hash=str(torrent_status.info_hashes.get_best())
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
            #return f"{self.status_label} ({self.progress}% complete) • DL {filters.do_filesizeformat(self.download_speed)}/s UP {filters.do_filesizeformat(self.upload_speed)}/s from {self.peers_count} peers"
            return f"{self.status_label} ({self.progress}% complete) at {filters.do_filesizeformat(self.download_speed)}/s from {self.peers_count} peers"
        
    def __str__(self):
        return f'{self.name} ({self.status_label} {self.progress}%)'


class TorrentClientError(Exception):
    pass

class TorrentClient(Thread):
    """
    Wrap the torrent client within a thread
    """

    def __init__(self, add_callback=nop_callback, update_callback=nop_callback, done_callback=nop_callback):
        super().__init__(name="TorrentClient worker")
        self.app = current_app._get_current_object()
        self.abort_event = Event()        
        self.download_dir = self.app.config.get('TORRENT_DOWNLOAD_DIR', Path.home())
        self.add_callback = add_callback
        self.update_callback = update_callback
        self.done_callback = done_callback 
        self.last_save_resume_data = time.time()

        alert_mask = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS | ALERT_MASK_STATUS

        session_params = {
            'user_agent': TORRENT_USER_AGENT_STRING,
            'listen_interfaces': f'0.0.0.0:{self.app.config.get('TORRENT_PORT', TORRENT_DEFAULT_PORT)}',
            'download_rate_limit': self.app.config.get('TORRENT_MAX_DOWNLOAD_RATE', 0) * 1024, # Default is unconstrained
            'upload_rate_limit': self.app.config.get('TORRENT_MAX_UPLOAD_RATE', 0) * 1024, # Default is unconstrained
            'alert_mask': alert_mask,
            # 256 blocks, reduce 'have_piece' messages to give false positives
            'cache_size': 4096 // 16,
            'connections_limit': MAX_CONNECTIONS,
            'peer_fingerprint': lt.generate_fingerprint(*TORRENT_USER_AGENT),
            # 'share_ratio_limit': 100, # The amounth of seeded is the same as download
            # 'seed_time_ratio_limit': 200, # Double the time as downloader 
            # 'seed_time_limit': 60 * 60, # Seconds
        }

        self.session = lt.session(session_params)

        for router, port in DHT_ROUTERS:
            self.session.add_dht_router(router, port)

    def abort(self):
        self.abort_event.set()

    def resume_torrents(self):
        """
        Add any incomplete torrent back to session
        """
        for torrent in models.get_incomplete_torrents():
            # Skip this torrent if we have no data to resume
            if torrent.resume_data:
                params = lt.read_resume_data(torrent.resume_data)
                self.session.async_add_torrent(params)
            else:
                self.app.logger.warn(f"No resume data found for '{torrent.release.name}', skipped")
    @property
    def torrents(self):
        return map(self._make_torrent, self.session.get_torrents())

    # def pause_torrent(self, handle, graceful_pause=True):
    #     handle.save_resume_data()
    #     handle.pause(1 if graceful_pause else 0)

    def pause(self, graceful_pause=True):
        # Pausing the session has the same effect as pausing every torrent in it, see:
        #  https://libtorrent.org/reference-Session.html#resume-is-paused-pause
        for handle in self.session.get_torrents():
            # Ask to save all resume data first
            handle.save_resume_data()
        self.session.pause()

    def run(self):
        self.session.start_dht()
        self.session.start_lsd()
        self.session.start_upnp()
        self.session.start_natpmp()

        # Keep checking for torrent events
        while not self.abort_event.is_set():
            # @@TODO Wait up to half a second to check again for alerts
            # self.session.wait_for_alert(500)
            alerts = self.session.pop_alerts()
            for a in alerts:
                if isinstance(a, lt.add_torrent_alert):
                    self.on_add_torrent_alert(a.handle)

                elif isinstance(a, lt.state_update_alert):
                    # Update caller for torrents that have changed their state
                    for status in a.status:
                        self.update_callback(Torrent(status))

                elif isinstance(a, lt.metadata_received_alert):
                    self.on_metadata_received_alert(a.handle)

                elif isinstance(a, lt.torrent_finished_alert):
                    self.on_torrent_finished_alert(a.handle)           

                elif isinstance(a, lt.save_resume_data_alert):
                    self.on_save_resume_data_alert(a)

                elif isinstance(a, lt.save_resume_data_failed_alert):
                    self.on_save_resume_data_failed_alert(a)

                elif isinstance(a, lt.torrent_removed_alert):                
                    info_hash = str(a.info_hashes.get_best())
                    self.on_torrent_removed_alert(info_hash)

            # Ask for torrent status updates only if there's something to transfer
            handlers = self.session.get_torrents()
            if handlers:                
                self.session.post_torrent_updates()
                now = time.time()
                if (now - self.last_save_resume_data) > SAVE_RESUME_DATA_INTERVAL:
                    self.app.logger.debug(f"Force saving resume data for {len(handlers)} torrents")
                    # @@TODO Do not save resume data for paused torrents -- check handle.flags()     
                    for handle in handlers:
                        #handle.flags()            
                        handle.save_resume_data()
                    self.last_save_resume_data = now

            # Wait a bit and check again
            time.sleep(0.75)

        self.pause()
        self.app.logger.debug(f"Stopped {self.name} #{id(self)} thread")

    # ---------------------
    # Torrent alerts
    # ---------------------

    def on_add_torrent_alert(self, handle):
        handle.set_max_connections(MAX_CONNECTIONS_PER_TORRENT)
        handle.unset_flags(lt.torrent_flags.auto_managed)
        self.add_callback(self._make_torrent(handle))

    def on_metadata_received_alert(self, handle):        
        # @@TODO Drop metadata step and switch to P for partial download 
        models.update_torrent_status(str(handle.info_hash()), models.TORRENT_GOT_METADATA)
        handle.save_resume_data()

    def on_save_resume_data_alert(self, alert):
        # Sanity check
        #if alert.handle.is_valid():
        info_hash = str(alert.handle.info_hash())
        data = lt.write_resume_data_buf(alert.params)
        done = models.update_torrent_resume_data(str(info_hash), data)
        self.app.logger.debug(f"Saved resume data for {alert.torrent_name} torrent")

    def on_save_resume_data_failed_alert(self, alert):
        self.app.logger.warn(f"Could not save resume data for torrent {alert.handle.info_hash()}, error was {alert.error}")

    def on_torrent_finished_alert(self, handle):
        done = models.update_torrent_status(str(handle.info_hash()), models.TORRENT_DOWNLOADED)
        # Possibly ask to save fast resume data before pausing the torrent
        #   so we have database coherent from what is saved on file
        #handle.save_resume_data() 
        handle.pause(1)
        self.done_callback(Torrent(handle.status()))     

    def on_torrent_removed_alert(self, info_hash):
        models.remove_torrent(info_hash)                    
        self.app.logger.debug(f"Removed torrent {info_hash}")

    # ---------------------
    # Adding and removing torrents
    # ---------------------

    def add_torrents(self, releases):
        for r in releases:
            self._add_torrent(r)

    def remove_torrent(self, info_hash, delete_files=False):
        torrent_handle = self.session.find_torrent(lt.sha1_hash(bytes.fromhex(info_hash)))
        if torrent_handle.is_valid():
            self.session.remove_torrent(torrent_handle, delete_files)
        else:
            raise TorrentClientError(f'Invalid torrent {info_hash}')

    # ---------------------
    # Helpers
    # ---------------------

    def _add_torrent(self, release):
        new_torrent = models.add_torrent(release)
        self.app.logger.debug(f"Started download for {new_torrent}")
        params = lt.parse_magnet_uri(release.magnet_uri)
        params.save_path = self.download_dir
        # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t        
        # params.storage_mode = lt.storage_mode_t.storage_mode_sparse 
        self.session.async_add_torrent(params)

    def _make_torrent(self, handle):
        if handle.is_valid():  # @@FIXME Or use handle.in_session()?
            torrent_status = handle.status()
            return Torrent(torrent_status)
        else:
            raise TorrentClientError(
                f"Invalid torrent handle {handle.id}")
                