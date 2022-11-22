import kivy
kivy.require('2.1.0')

from kivy.logger import Logger, LOG_LEVELS

from kivy.app import App
from kivy.logger import Logger
import configuration
import sync
import model
import os
from pubsub import pub
#import torrenter
from dataclasses import dataclass
import views

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

        #return controllers.Home(featured_series=featured_series)
        return views.Videobox()

    def is_syncing(self):
        return self.sync_worker and self.sync_worker.is_alive()

    def start_sync(self):
        if self.is_syncing():
            Logger.debug("Synchronization is running, ignored request")
        else:
            self.sync_worker = sync.SyncWorker(
                progress_callback=self.on_sync_progress, done_callback=self.sync_ended)
            self.sync_worker.start()
                    
    def on_sync_progress(self, message, percent=None):
        #Logger.info(f"{message} {percent}")
        pass
    
    def sync_ended(self, result):
        # message = wx.adv.NotificationMessage(self.AppName, res5ult)
        pass

if __name__ == '__main__':
    
    # Logger.basicConfig(level=configuration.log_level)
    # for module in ['peewee', 'requests', 'urllib3', 'PIL']:
    #     # Set higher log level for deps
    #     Logger.getLogger(module).setLevel(Logger.WARN)

    Logger.setLevel(LOG_LEVELS["debug"])

    VideoboxApp().run()
