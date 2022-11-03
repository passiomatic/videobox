import requests 
import logging 
from threading import Thread
from queue import SimpleQueue
import wx
from io import BytesIO
import os 
import hashlib

class ImageCache(object):
    """
    Grab image from the local cache or fetch from given URL queueing requests
    """

    def __init__(self, cache_dir, default, values=None):
        self.images = values if values else {}
        self.default = default
        self.cache_dir = cache_dir
        self.download_queue = SimpleQueue()
        self.worker = Thread(target=self.worker, name="Cache worker", daemon=True)
        self.worker.start()

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
                data = BytesIO(r.content)
                image = wx.Image(data)
                self.set(url, image)
                # @@TODO Or use r.headers['Content-Type']? 
                self.store_image(url, r.content, image.GetType())
            else:
                logging.debug("Got status {0}, skipped".format(r.status_code))
    
    def store_image(self, url, data, image_type):
        # MD5 here since the filename is shorter not collision-critical
        filename = "{0}.{1}".format(hashlib.md5(url.encode("utf-8")).hexdigest(), self.get_image_extension(image_type))
        with open(os.path.join(self.cache_dir, filename), "wb") as output:
            output.write(data)
            logging.debug("Stored new image {0}".format(filename))
    
    def get_image_extension(self, image_type):
        if image_type == wx.BITMAP_TYPE_PNG:
            return "png"
        elif image_type == wx.BITMAP_TYPE_JPEG:
            return "jpg"
        else:
            logging.warn("Unrecognized image type {0}, skipped".format(image_type))
            return ""

