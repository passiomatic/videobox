from dataclasses import dataclass
import requests 
import logging 
from threading import Thread
from queue import SimpleQueue
import wx
from io import BytesIO
import os 
import hashlib
from PIL import Image

INPUT_IMAGE_FORMATS = ['JPEG', 'JPEG2000', 'PNG']

@dataclass
class RemoteImage:
    url: str
    width: int
    height: int

    # @@TODO Call this instead of ImageCache.make_digest?
    def make_digest(self):
        # MD5 here since the filename is shorter and not collision-critical
        return hashlib.md5(self.url.encode("utf-8")).hexdigest()

    def __str__(self):
        return self.url


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
        if not url:
            logging.debug("Empty image URL, skipped")
            return default

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
                # Schedule for fetching using default image dimensions as reference
                remote_image = RemoteImage(url=url, width=default.Width, height=default.Height)
                self.download_queue.put(remote_image)
                logging.info("Could not find image {0} in cache, added to download queue".format(url))
                return default

    # def add(self, url):
    #     # Schedule URL for fetching
    #     self.download_queue.put(url)
    #     logging.debug("Could not find image {0} in cache, added to download queue".format(url))

    def set(self, digest, image):
        self.images[digest] = image

    def worker(self):
        while True: 
            remote_image = self.download_queue.get()
            logging.debug(f"Fetching image {remote_image}...")
            r = requests.get(remote_image.url)            
            digest = self.make_digest(remote_image.url)
            if r.status_code == 200:                 
                image = self.save_image(digest, r.content, r.headers['Content-Type'], (remote_image.width, remote_image.height))
                self.set(digest, image)
            else:
                # Don't keep asking for broken images
                self.set(digest, None)
                logging.debug("Got status {0}, skipped".format(r.status_code))
    
    def save_image(self, digest, bytes, image_type, size):
        # @@TODO use image_type as format hint?
        buffer = BytesIO(bytes)
        filename = f"{digest}.jpg"
        image = Image.open(buffer, formats=INPUT_IMAGE_FORMATS)
        # Scale down to desired size
        image.thumbnail(size)
        image.save(os.path.join(self.cache_dir, filename), "JPEG", quality=75, optimize=True)  
        logging.debug(f"Saved new image {filename}")

        wx_image = wx.Image(image.width, image.height, image.convert("RGB").tobytes())
        return wx_image

    def load_image(self, digest):
        # @@TODO Don't guess extension
        filename = f"{digest}.jpg"
        with open(os.path.join(self.cache_dir, filename), "rb") as input:
            image = wx.Image(input)
            logging.debug(f"Loaded image from cache {filename}")
            return image
    
    # def get_image_suffix(self, image_type):
    #     if image_type == wx.BITMAP_TYPE_PNG:
    #         return "png"
    #     elif image_type == wx.BITMAP_TYPE_JPEG:
    #         return "jpg"
    #     else:
    #         logging.warn("Unrecognized image type {0}, skipped".format(image_type))
    #         return ""

    def make_digest(self, url):
        # MD5 here since the filename is shorter and not collision-critical
        return hashlib.md5(url.encode("utf-8")).hexdigest()