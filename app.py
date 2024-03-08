import webbrowser 
import os
from threading import Thread
import rumps
import requests
import videobox
import videobox.sync as sync

APP_SERVER_PORT = 9157
APP_URL = f"http://127.0.0.1:{APP_SERVER_PORT}"
MAX_WORKER_TIMEOUT = 10 # Seconds

class VideoboxApp(rumps.App):
    @rumps.clicked("Open Web Interface")
    def open_web_interface(self, _):
        webbrowser.open_new(APP_URL)

    @rumps.events.on_wake
    def on_wake(self):
        #print('=== VideoboxApp: on_wake ===')
        # Force a library sync
        requests.post(f"{APP_URL}/sync")

    @rumps.events.before_quit
    def before_quit(self):
        #print('=== VideoboxApp: before_quit ===')
        # Sanity check since Flask app startup could go wrong
        if sync.sync_worker:
            sync.sync_worker.abort()
            if sync.sync_worker.is_alive():
                sync.sync_worker.join(MAX_WORKER_TIMEOUT)

if __name__ == "__main__":
    data_dir = rumps.application_support("Videobox")
    waitress_worker = Thread(name="Waitress worker",
                             target=videobox.run_app, daemon=False, 
                             kwargs={'base_dir': os.getcwd(), 'data_dir': data_dir, 'port': APP_SERVER_PORT})
    waitress_worker.start()
    #VideoboxApp("Videobox", icon="menubar-icon.svg", template=True).run(debug=True)
    VideoboxApp("Videobox", icon="menubar-icon.svg", template=True).run()