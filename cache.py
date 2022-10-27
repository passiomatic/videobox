class ImageCache():
    """
    Grab image from the local cache or fetch from given URL
    """

    def __init__(self, default, values=None):
        self.images = values if values else {}
        self.default  = default

    def get(self, url):
        try:
            # Schedule for fetching

            return self.images[url]
        except KeyError:
            return self.default

    def add(self, url):
        self.images[url] = self.default

    def set(self, url, image):
        self.images[url] = image



