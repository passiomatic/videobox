import kivy
kivy.require('2.1.0')

from kivy.app import App
import logging
import configuration
import sync
import model
import os
from pubsub import pub
#import torrenter
from dataclasses import dataclass
import controllers

class VideoboxApp(App):
    pass

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
        logging.info(f"Cache dir is {self.cache_dir}")

        os.makedirs(self.download_dir, exist_ok=True)
        logging.info(f"Download dir is {self.download_dir}")

        model.connect(app_dir, shouldSetup=True)

        featured_series = model.get_featured_series(7)[:12]
        return controllers.Home(featured_series=featured_series)


if __name__ == '__main__':
    
    logging.basicConfig(level=configuration.log_level)
    for module in ['peewee', 'requests', 'urllib3', 'PIL']:
        # Set higher log level for deps
        logging.getLogger(module).setLevel(logging.WARN)

    VideoboxApp().run()
