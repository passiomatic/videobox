import os
from threading import Thread, Event
import time
from pathlib import Path
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
SAVE_RESUME_DATA_INTERVAL = 300 # Seconds

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

ALERT_MASK = ALERT_MASK_ERROR | ALERT_MASK_PROGRESS | ALERT_MASK_STATUS
RESUME_DATA_MASK = lt.torrent_handle.save_info_dict | lt.torrent_handle.only_if_modified

STATE_LABELS = {
    lt.torrent_status.states.checking_files: "Checking files",
    lt.torrent_status.states.downloading_metadata: "Fetching metadata",
    lt.torrent_status.states.downloading: "Downloading",
    lt.torrent_status.states.finished: "Finished", # Cannot seed, we have an incomplete torrent!
    lt.torrent_status.states.seeding: "Seeding",
    lt.torrent_status.states.checking_resume_data: "Checking resume data",
}

torrent_worker = None

class Transfer(object):
    """
    An ongoing data transfer using the BitTorrent protocol
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

    def get_filenames(self):
        torrent_file = self.handle.torrent_file()
        if torrent_file:
            file_storage = torrent_file.files()
            return [file_storage.file_path(index) for index in range(file_storage.num_files())]
        else:
            raise TorrentClientError(
                f"Torrent {self.handle} has no metatada yet")

    @property
    def stats(self):
        if self.status == lt.torrent_status.states.seeding:
            return f"{self.status_label} at {filters.do_filesizeformat(self.upload_speed)}/s to {self.peers_count} peers"
        elif self.status == lt.torrent_status.states.downloading_metadata:
            return f"{self.status_label} from {self.peers_count} peers"
        else:
            #return f"{self.status_label} ({self.progress}% complete) • DL {filters.do_filesizeformat(self.download_speed)}/s UP {filters.do_filesizeformat(self.upload_speed)}/s from {self.peers_count} peers"
            return f"{self.status_label} ({self.progress}% complete) at {filters.do_filesizeformat(self.download_speed)}/s from {self.peers_count} peers"
        
    def __str__(self):
        return f'{self.name} ({self.status_label})'


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
        self.session = lt.session(self._make_session_params())
        self.last_save_resume_data = time.time()

        for router, port in DHT_ROUTERS:
            self.session.add_dht_router(router, port)

    def abort(self):
        self.abort_event.set()

    def resume_torrents(self):
        """
        Add any incomplete torrent back to session
        """
        for torrent in models.get_incomplete_torrents():
            # @@TODO Re-add torrent if resume data is missing or mark torrent as TORRENT_ABORTED? 
            if torrent.resume_data:
                params = lt.read_resume_data(torrent.resume_data)
                self.session.async_add_torrent(params)
                self.app.logger.debug(f"Resumed torrent '{torrent}'")
            else:
                self.app.logger.warn(f"No resume data found for '{torrent}', skipped")
    
    @property
    def transfers(self):
        """
        List of transfers being downloaded
        """
        return [self._make_transfer(handle) for handle in self.session.get_torrents()]

    # def pause_torrent(self, handle, graceful_pause=True):
    #     handle.save_resume_data()
    #     handle.pause(1 if graceful_pause else 0)

    def pause(self):
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
            alerts = self.session.pop_alerts()
            for a in alerts:
                if isinstance(a, lt.add_torrent_alert):
                    self.on_add_torrent_alert(a.handle)

                elif isinstance(a, lt.state_update_alert):
                    # Update caller for torrents that have changed their state
                    for status in a.status:
                        self.update_callback(Transfer(status))

                elif isinstance(a, lt.metadata_received_alert):
                    self.on_metadata_received_alert(a.handle)

                elif isinstance(a, lt.torrent_finished_alert):
                    self.on_torrent_finished_alert(a.handle)           

                elif isinstance(a, lt.torrent_paused_alert):
                    pass

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
                    self.app.logger.debug(f"Asked saving resume data for {len(handlers)} torrents")
                    for handle in handlers:
                        handle.save_resume_data(RESUME_DATA_MASK)
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
        transfer = self._make_transfer(handle)
        self.add_callback(transfer)

    def on_metadata_received_alert(self, handle):        
        transfer = Transfer(handle.status())
        # filenames = transfer.get_filenames()
        # if len(filenames) == 1:
        #     filename = filenames[0]
        # else:
        #     filename = os.path.commonprefix(filenames)
        # download_path = os.path.join(self.download_dir, filename)
        models.update_torrent(transfer.info_hash, status=models.TORRENT_GOT_METADATA)
        # Ask to save metadata immediately
        handle.save_resume_data(lt.torrent_handle.save_info_dict)

    def on_save_resume_data_alert(self, alert):
        info_hash = str(alert.handle.info_hash())
        data = lt.write_resume_data_buf(alert.params)
        did_update = models.update_torrent(info_hash, resume_data=data)
        if did_update:
            self.app.logger.debug(f"Saved resume data for {alert.torrent_name} torrent")

    def on_save_resume_data_failed_alert(self, alert):
        self.app.logger.debug(f"Skipped save resume data for torrent, reason was: {alert.message()}")

    def on_torrent_finished_alert(self, handle):
        transfer = Transfer(handle.status())
        did_update = models.update_torrent(transfer.info_hash, status=models.TORRENT_DOWNLOADED)
        # Possibly ask to save fast resume data before pausing the torrent
        #   so we have database coherent from what is saved on file
        handle.save_resume_data() 
        handle.pause(1)
        self.done_callback(transfer)     

    def on_torrent_removed_alert(self, info_hash):
        did_remove = models.remove_torrent(info_hash)                    
        self.app.logger.debug(f"Removed torrent {info_hash}")

    # ---------------------
    # Adding and removing torrents
    # ---------------------

    def add_torrents(self, releases):
        for r in releases:
            self._add_torrent(r)

    def remove_torrent(self, info_hash, delete_files=False):
        torrent_handle = self._find_torrent(info_hash)
        if torrent_handle.is_valid():
            self.session.remove_torrent(torrent_handle, delete_files)
        else:
            raise TorrentClientError(f'Invalid torrent handle for {info_hash}')

    # ---------------------
    # Helpers
    # ---------------------

    def _find_torrent(self, info_hash):
        # If torrent cannot be found, an invalid torrent_handle is returned
        return self.session.find_torrent(lt.sha1_hash(bytes.fromhex(info_hash)))

    def _make_session_params(self):
        return {
            'user_agent': TORRENT_USER_AGENT_STRING,
            'listen_interfaces': f'0.0.0.0:{self.app.config.get('TORRENT_PORT', TORRENT_DEFAULT_PORT)}',
            'download_rate_limit': self.app.config.get('TORRENT_MAX_DOWNLOAD_RATE', 0) * 1024, # Default is unconstrained
            'upload_rate_limit': self.app.config.get('TORRENT_MAX_UPLOAD_RATE', 0) * 1024, # Default is unconstrained
            'alert_mask': ALERT_MASK,            
            'cache_size': 4096 // 16, # 256 blocks, reduce 'have_piece' messages to give false positives
            'connections_limit': MAX_CONNECTIONS,
            'peer_fingerprint': lt.generate_fingerprint(*TORRENT_USER_AGENT),
        }            

    def _add_torrent(self, release):
        new_torrent = models.add_torrent(release)
        params = lt.parse_magnet_uri(release.magnet_uri)
        params.save_path = self.download_dir
        # Default mode https://libtorrent.org/reference-Storage.html#storage_mode_t        
        # params.storage_mode = lt.storage_mode_t.storage_mode_sparse 
        self.app.logger.debug(f"Added torrent '{new_torrent}'")
        self.session.async_add_torrent(params)

    def _make_transfer(self, handle):
        if handle.is_valid():  # @@FIXME Or use handle.in_session()?
            torrent_status = handle.status()
            return Transfer(torrent_status)
        else:
            raise TorrentClientError(
                f"Invalid torrent handle {handle.id}")
                