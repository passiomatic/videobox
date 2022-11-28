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

    def on_start(self):        
        self.sync_worker = None

        # During development prefer using local directories
        #if configuration.DEBUG:
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

        return super().on_start()

    def on_release_clicked(self, info_hash):
        release = model.get_release(info_hash)
        self.torrenter.add_torrent(self.download_dir, release.magnet_uri)

    def on_torrent_add(self, torrent):
        release = model.get_release(torrent.info_hash)
        # @@TODO query_save_path to retrieve path
        #transfer = model.Transfer.create(release=release, path='')

    def on_torrent_update(self, torrent):
        #self.frame.UpdateDownloadsPanel()
        pass

    def on_torrent_done(self, torrent):
        #self.frame.UpdateDownloadsPanel()
        Logger.debug(f"DOWNLOADED {torrent.name}")
        # message = wx.adv.NotificationMessage(
        #     self.AppName, f"Torrent {torrent.name} has been downloaded")
        # message.Show()

    def build(self):
        self.icon = 'icon.png'        
        return super().build()

    def on_stop(self):
        # Wait a bit for Torrenter instance to shutdown
        self.torrenter.keep_running = False
        self.torrenter.join(5)
        Logger.debug("Exiting app")

    def is_syncing(self):
        return self.sync_worker and self.sync_worker.is_alive()

    def start_sync(self):
        if self.is_syncing():
            Logger.debug("Synchronization is running, ignored request")
        else:
            self.sync_worker = sync.SyncWorker(
                progress_callback=self.on_sync_progress, done_callback=self.on_sync_ended)
            self.sync_worker.start()

    def on_sync_progress(self, message, dt):
        Logger.info(f"{message}")

    def on_sync_ended(self, result, dt):
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
