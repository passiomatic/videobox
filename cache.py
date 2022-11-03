import requests 
import logging 
from threading import Thread
from queue import SimpleQueue
import wx
from io import BytesIO

class ImageCache(object):
    """
    Grab image from the local cache or fetch from given URL queueing requests
    """

    def __init__(self, default, values=None):
        self.images = values if values else {}
        self.default = default
        self.download_queue = SimpleQueue()
        self.worker = Thread(target=self.worker, name="Cache worker", daemon=True)
        #self.worker.start()

    def get(self, url):
        try:
            return self.images[url]
        except KeyError:
            # Schedule for fetching
            self.download_queue.put(url)
            logging.info("Could not find image {0} in cache, added to download queue".format(url))
            return self.default

    def set(self, url, image):
        self.images[url] = image

    def worker(self):
        while True: 
            url = self.download_queue.get()
            logging.debug("Fetching image {0}...".format(url))
            r = requests.get(url)            
            if r.status_code == 200: 
                bytes = BytesIO(r.content)
                image = wx.Image(bytes, 'image/jpeg')
                self.set(url, image)
            else:
                logging.debug("Got status {0}, skipped".format(r.status_code))