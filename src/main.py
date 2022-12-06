from pubsub import pub
import os
import model
import sync
import configuration
import torrenter
from kivy.app import App
from kivy.logger import Logger, LOG_LEVELS
import kivy
from peewee import IntegrityError
from plyer import notification
import uuid
from pathlib import Path
import views # Needed to resolve app widget classes
kivy.require('2.1.0')

VIDEO_EXTENSIONS = [
    '.webm', '.mkv', '.flv', '.avi', '.mpg', '.mp2', '.mpeg', '.mpe', '.mpv', '.m2v', '.m4v'
]

class VideoboxApp(App):
    
    kv_directory = "kv"

    # ------------------
    # App life-cycle
    # ------------------

    def on_start(self):
        self.sync_worker = None

        self.download_dir = Path.home().joinpath("Downloads")                
        self.download_dir.mkdir(exist_ok=True)
        Logger.info(f"App: Download dir is {self.download_dir}")

        options = {}
        options['save_dir'] = str(self.download_dir)
        options['add_callback'] = self.on_torrent_add
        options['update_callback'] = self.on_torrent_update
        options['done_callback'] = self.on_torrent_done

        self.torrent_client = torrenter.TorrentClient(options)
        self.torrent_client.load_torrents()

        # @@TODO https://groups.google.com/g/kivy-users/c/yT1oweFIaqU
        #self.root_window.maximize()

    def build(self):
        self.icon = 'icon.png'        
        self.client_id = self.config.get('sync', 'client_id')
        return super().build()

    def on_stop(self):
        # Wait a bit for TorrentClient instance to shutdown
        self.torrent_client.keep_running = False
        self.torrent_client.join(5)
        Logger.debug("App: Exiting")

    def build_config(self, config):
        config.setdefaults('sync', {
            'client_id': uuid.uuid1().hex,            
        })
        
    # ------------------
    # Torrent handling
    # ------------------

    def on_release_clicked(self, id):
        release = model.get_release(id)
        try:
            torrent = model.Torrent.create(release=release)
            self.torrent_client.add_torrent(release.magnet_uri)
        except IntegrityError as ex:
            Logger.warning(
                f"App: Torrent {release.name} already added, skipped")

    def on_torrent_add(self, torrent, dt):
        #release = model.get_release_with_info_hash(torrent.info_hash)
        #pub.sendMessage(torrenter.MSG_TORRENT_ADD, torrent)
        # @@TODO query_save_path to retrieve path
        pass

    def on_torrent_update(self, torrent, dt):        
        pub.sendMessage(torrenter.MSG_TORRENT_UPDATE, torrents=self.torrent_client.torrents_status)

    def on_torrent_done(self, torrent, dt):
        #pub.sendMessage(torrenter.MSG_TORRENT_DONE, torrent=torrent)
        # torrent = model.get_next_playable_torrent()
        # if torrent:
        # else:
        #     Logger.warn("Could not get next torrent to play")
        filename, size = self.find_best_media_file(torrent.get_files())
        Logger.debug(f"App: Ready to play {filename}")
        notification.notify(title="Download finished",
                            message=f"{torrent.name} is ready for playback", timeout=5)        

    def find_best_media_file(self, files):
        # Sort by size and pick the biggest one
        return sorted(files, key=lambda a: a[1], reverse=True)[0]


    # ------------------
    # Syncing
    # ------------------

    def is_syncing(self):
        return self.sync_worker and self.sync_worker.is_alive()

    def start_sync(self):
        if self.is_syncing():
            Logger.warn("App: Synchronization is running, ignored request")
        else:
            self.sync_worker = sync.SyncWorker(client_id=self.client_id,
                progress_callback=self.on_sync_progress, done_callback=self.on_sync_ended)
            self.sync_worker.start()

    def on_sync_progress(self, message, dt):
        Logger.info(f"App: {message}")

    def on_sync_ended(self, result, dt):
        notification.notify(title="Sync finished",
                            message=result, timeout=10)

if __name__ == '__main__':

    if configuration.DEBUG:
        Logger.setLevel(LOG_LEVELS["debug"])

    app_dir = os.getcwd()
    model.connect(app_dir, should_setup=True)

    VideoboxApp().run()
