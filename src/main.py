from dataclasses import dataclass
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
import views # Needed to lookup Kivy widget classes
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
        # self.torrenter.load_torrents()

        # @@TODO https://groups.google.com/g/kivy-users/c/yT1oweFIaqU
        #self.root_window.maximize()

    def build(self):
        self.icon = 'icon.png'
        self.client_id = self.config.get('sync', 'client_id')
        return super().build()

    def on_stop(self):
        # Wait a bit for Torrenter instance to shutdown
        self.torrenter.keep_running = False
        self.torrenter.join(5)
        Logger.debug("Exiting app")

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
            transfer = model.Transfer.create(release=release)
            self.torrenter.add_torrent(release.magnet_uri)
        except IntegrityError as ex:
            Logger.warning(
                f"Torrent {release.original_name} already added to transfers, skipped")

    def on_torrent_add(self, torrent, dt):
        #release = model.get_release_with_info_hash(torrent.info_hash)
        #pub.sendMessage(torrenter.MSG_TORRENT_ADD, torrent)
        # @@TODO query_save_path to retrieve path
        pass

    def on_torrent_update(self, torrent, dt):        
        pub.sendMessage(torrenter.MSG_TORRENT_UPDATE, torrents=self.torrenter.torrents_status)

    def on_torrent_done(self, torrent, dt):
        #pub.sendMessage(torrenter.MSG_TORRENT_DONE, torrent=torrent)
        Logger.debug(f"files={torrent.get_files()}")
        notification.notify(title="Download finished",
                            message=f"{torrent.name} is ready for playback", app_name=self.name, timeout=5)        

    # ------------------
    # Syncing
    # ------------------

    def is_syncing(self):
        return self.sync_worker and self.sync_worker.is_alive()

    def start_sync(self):
        if self.is_syncing():
            Logger.warn("Synchronization is running, ignored request")
        else:
            self.sync_worker = sync.SyncWorker(client_id=self.client_id,
                progress_callback=self.on_sync_progress, done_callback=self.on_sync_ended)
            self.sync_worker.start()

    def on_sync_progress(self, message, dt):
        Logger.info(f"{message}")

    def on_sync_ended(self, result, dt):
        notification.notify(title="Sync finished",
                            message=result, app_name=self.name, timeout=10)

if __name__ == '__main__':

    if configuration.DEBUG:
        Logger.setLevel(LOG_LEVELS["debug"])

    app_dir = os.getcwd()
    model.connect(app_dir, should_setup=True)

    VideoboxApp().run()
