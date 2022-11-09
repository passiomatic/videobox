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

    def __init__(self, cache_dir, values=None):
        self.images = values if values else {}
        self.cache_dir = cache_dir
        self.download_queue = SimpleQueue()
        self.worker = Thread(target=self.worker, name="Cache worker", daemon=True)
        self.worker.start()

    def get(self, url, default):
        digest = self.make_digest(url)
        try:
            image = self.images[digest]
            if image:
                return image
            else:
                return default
        except KeyError:
            try:
                # Lookup local cache 
                image = self.load_image(digest)
                self.set(digest, image)
                return image
            except FileNotFoundError:
                # Schedule for fetching
                self.download_queue.put(url)
                logging.info("Could not find image {0} in cache, added to download queue".format(url))
                return default

    def set(self, digest, image):
        self.images[digest] = image

    def worker(self):
        while True: 
            url = self.download_queue.get()
            logging.debug("Fetching image {0}...".format(url))
            r = requests.get(url)            
            digest = self.make_digest(url)
            if r.status_code == 200: 
                data = BytesIO(r.content)
                image = wx.Image(data)
                self.set(digest, image)
                # @@TODO Or use r.headers['Content-Type']? 
                self.save_image(digest, r.content, image.GetType())
            else:
                # Don't keep asking for broken images
                self.set(digest, None)
                logging.debug("Got status {0}, skipped".format(r.status_code))
    
    def save_image(self, digest, data, image_type):
        suffix = self.get_image_suffix(image_type)
        if suffix:
            filename = f"{digest}.{suffix}"
            with open(os.path.join(self.cache_dir, filename), "wb") as output:
                output.write(data)
                logging.debug("Stored new image {0}".format(filename))

    def load_image(self, digest):
        # @@TODO Don't guess extension
        filename = f"{digest}.jpg"
        with open(os.path.join(self.cache_dir, filename), "rb") as input:
            image = wx.Image(input)
            logging.debug(f"Loaded image from cache {filename}")
            return image

    def get_image_suffix(self, image_type):
        if image_type == wx.BITMAP_TYPE_PNG:
            return "png"
        elif image_type == wx.BITMAP_TYPE_JPEG:
            return "jpg"
        else:
            logging.warn("Unrecognized image type {0}, skipped".format(image_type))
            return ""

    def make_digest(self, url):
        # MD5 here since the filename is shorter and not collision-critical
        return hashlib.md5(url.encode("utf-8")).hexdigest()