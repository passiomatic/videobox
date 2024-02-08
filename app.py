import webbrowser 
import os
from threading import Thread
import rumps
import videobox

APP_SERVER_PORT = 9157

class VideoboxApp(rumps.App):
    @rumps.clicked("Open Web Interface")
    def open_web_interface(self, _):
        webbrowser.open_new(f"http://127.0.0.1:{APP_SERVER_PORT}")

    # @rumps.events.on_wake
    # def on_wake(self):
    #     print('=== app class: on_wake ===')
        
if __name__ == "__main__":
    data_dir = rumps.application_support("Videobox")
    waitress_worker = Thread(name="Waitress worker",
                             target=videobox.run_app, daemon=False, 
                             kwargs={'base_dir': os.getcwd(), 'data_dir': data_dir, 'port': APP_SERVER_PORT})
    waitress_worker.start()
    #VideoboxApp("Videobox", icon="menubar-icon.svg", template=True).run(debug=True)
    VideoboxApp("Videobox", icon="menubar-icon.svg", template=True).run()