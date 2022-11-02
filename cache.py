import requests 
import logging 
from threading import Thread
from queue import SimpleQueue

class ImageCache(object):
    """
    Grab image from the local cache or fetch from given URL queueing requests
    """

    def __init__(self, default, values=None):
        self.images = values if values else {}
        self.default = default
        self.download_queue = SimpleQueue()
        self.worker = Thread(target=self.worker, name="Cache worker", daemon=True)
        self.worker.start()

    def get(self, url):
        try:
            # Already in cache
            return self.images[url]
        except KeyError:
            # Schedule for fetching
            self.download_queue.put(url)
            logging.debug("Could not find cached image URL {0}, using default".format(url))
            return self.default

    def set(self, url, image):
        self.images[url] = image

    def worker(self):
        while True: 
            url = self.download_queue.get()
            logging.debug("Fetching image {0}...".format(url))
            r = requests.get(url)
            # r.content
            logging.debug(f"size is {self.download_queue.qsize()}")
            #self.set(url, wx.Image(r.content, "image/jpeg"))




