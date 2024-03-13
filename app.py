import webbrowser 
import os
from threading import Thread
import rumps
import waitress
import videobox
import videobox.sync as sync

APP_SERVER_PORT = 9157
APP_URL = f"http://127.0.0.1:{APP_SERVER_PORT}"

class VideoboxApp(rumps.App):
    def __init__(self, flask_app, name, title=None, icon=None, template=None, menu=None):
        self.flask_app = flask_app
        super().__init__(name, title, icon, template, menu)

    @rumps.clicked("Open Web Interface")
    def open_web_interface(self, _):
        webbrowser.open_new(APP_URL)

    @rumps.events.on_wake
    def on_wake(self):
        with self.flask_app.app_context():
            # Wait for the current worker to finish
            sync.sync_worker.abort()
            sync.sync_worker.join(videobox.MAX_WORKER_TIMEOUT)
            # Restart immediately with another worker
            sync.sync_worker = sync.SyncWorker(self.flask_app.config["API_CLIENT_ID"])
            sync.sync_worker.start()

    @rumps.events.before_quit
    def before_quit(self):
        videobox.shutdown_workers(self.flask_app)

if __name__ == "__main__":
    data_dir = rumps.application_support("Videobox")
    flask_app = videobox.create_app(app_dir=os.getcwd(), data_dir=data_dir)

    def runner():
        waitress.serve(flask_app, host='127.0.0.1', port=APP_SERVER_PORT, threads=8)

    # Start a local web server
    waitress_worker = Thread(name="Waitress worker", target=runner, daemon=False)
    waitress_worker.start()
    
    #VideoboxApp(flask_app, "Videobox", icon="menubar-icon.svg", template=True).run(debug=True)
    VideoboxApp(flask_app, "Videobox", icon="menubar-icon.svg", template=True).run()