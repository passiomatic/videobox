import kivy
kivy.require('2.1.0')

from kivy.uix.floatlayout import FloatLayout
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty

import logging
import configuration
import sync
import model
#from cache import ImageCache
import os
#import views.theme as theme
from pubsub import pub
#import torrenter
from dataclasses import dataclass


class Controller(FloatLayout):
    '''Create a controller that receives a custom widget from the kv lang file.

    Add an action to be called from the kv lang file.
    '''
    label_wid = ObjectProperty()
    info = StringProperty()

    def do_action(self):
        self.label_wid.text = 'My label after button press'
        self.info = 'New info text'


class ControllerApp(App):

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

        return Controller(info='Hello world')


if __name__ == '__main__':
    
    logging.basicConfig(level=configuration.log_level)
    for module in ['peewee', 'requests', 'urllib3', 'PIL']:
        # Set higher log level for deps
        logging.getLogger(module).setLevel(logging.WARN)

    ControllerApp().run()
