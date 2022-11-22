import views
from dataclasses import dataclass
from pubsub import pub
import os
import model
import sync
import configuration
from kivy.logger import Logger
from kivy.app import App
from kivy.logger import Logger, LOG_LEVELS
import kivy
kivy.require('2.1.0')


#import torrenter


class VideoboxApp(App):

    def build(self):
        self.sync_worker = None

        # During development prefer using local directories
        if configuration.DEBUG:
            app_dir = os.getcwd()
            self.cache_dir = os.path.join(app_dir, "Cache")
            self.download_dir = os.path.join(app_dir, "Transfers")
        # else:
        #     paths = wx.StandardPaths.Get()
        #     app_dir = paths.UserLocalDataDir
        #     self.cache_dir = os.path.join(paths.UserLocalDataDir, "Cache")
        #     self.download_dir = os.path.join(
        #         paths.AppDocumentsDir, "Transfers")

        os.makedirs(self.cache_dir, exist_ok=True)
        Logger.info(f"Cache dir is {self.cache_dir}")

        os.makedirs(self.download_dir, exist_ok=True)
        Logger.info(f"Download dir is {self.download_dir}")

        model.connect(app_dir, shouldSetup=True)

        return views.Videobox()
        # series = model.get_series(153021)
        # return views.SeriesDetail(id=series.tvdb_id, name=series.name, poster_url=series.poster_url, network=series.network.upper(), overview=series.overview)

    def on_stop(self):
        # The Kivy event loop is about to stop, set a stop signal;
        # otherwise the app window will close, but the Python process will
        # keep running until all secondary threads exit.
        pass

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

    Logger.setLevel(LOG_LEVELS["debug"])

    VideoboxApp().run()
