import views
from dataclasses import dataclass
from pubsub import pub
import os
import model
import sync
import configuration
import torrenter
from kivy.logger import Logger
from kivy.app import App
from kivy.logger import Logger, LOG_LEVELS
import kivy
kivy.require('2.1.0')


class VideoboxApp(App):

    # ------------------
    # App life-cycle
    # ------------------

    def on_start(self):
        self.sync_worker = None

        # During development prefer using local directories
        # if configuration.DEBUG:
        self.download_dir = os.path.join(os.getcwd(), "Transfers")

        # os.makedirs(self.cache_dir, exist_ok=True)
        # Logger.info(f"Cache dir is {self.cache_dir}")

        os.makedirs(self.download_dir, exist_ok=True)
        Logger.info(f"Transfers dir is {self.download_dir}")

        options = {}
        options['save_dir'] = self.download_dir
        options['add_callback'] = self.on_torrent_add
        options['update_callback'] = self.on_torrent_update
        options['done_callback'] = self.on_torrent_done

        self.torrenter = torrenter.Torrenter(options)
        self.torrenter.load_torrents()

    def build(self):
        self.icon = 'icon.png'
        return super().build()

    def on_stop(self):
        # Wait a bit for Torrenter instance to shutdown
        self.torrenter.keep_running = False
        self.torrenter.join(5)
        Logger.debug("Exiting app")

    # ------------------
    # Torrent handling
    # ------------------

    def on_release_clicked(self, id):
        release = model.get_release(id)
        self.torrenter.add_torrent(release.magnet_uri)
        
    def on_torrent_add(self, torrent, dt):
        release = model.get_release_with_info_hash(torrent.info_hash)
        # @@TODO query_save_path to retrieve path
        transfer = model.Transfer.create(release=release, path='')

    def on_torrent_update(self, torrent, dt):
        # self.frame.UpdateDownloadsPanel()
        #tranfers_view = self.ids.tranfers
        Logger.debug(f"{torrent.name} {torrent.progress}%")

    def on_torrent_done(self, torrent, dt):
        # self.frame.UpdateDownloadsPanel()
        Logger.debug(f"DOWNLOADED {torrent.name}")
        # message = wx.adv.NotificationMessage(
        #     self.AppName, f"Torrent {torrent.name} has been downloaded")
        # message.Show()

    # ------------------
    # Syncing
    # ------------------

    def is_syncing(self):
        return self.sync_worker and self.sync_worker.is_alive()

    def start_sync(self):
        if self.is_syncing():
            Logger.warn("Synchronization is running, ignored request")
        else:
            self.sync_worker = sync.SyncWorker(
                progress_callback=self.on_sync_progress, done_callback=self.on_sync_ended)
            self.sync_worker.start()

    def on_sync_progress(self, message, dt):
        Logger.info(f"{message}")

    def on_sync_ended(self, result, dt):
        # TODO: Show notification message
        # message = wx.adv.NotificationMessage(self.AppName, result)
        pass


if __name__ == '__main__':

    # Logger.basicConfig(level=configuration.log_level)
    # for module in ['peewee', 'requests', 'urllib3', 'PIL']:
    #     # Set higher log level for deps
    #     Logger.getLogger(module).setLevel(Logger.WARN)

    if configuration.DEBUG:
        Logger.setLevel(LOG_LEVELS["debug"])

    app_dir = os.getcwd()
    model.connect(app_dir, shouldSetup=True)

    VideoboxApp().run()
