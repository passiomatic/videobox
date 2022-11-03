import wx
import logging

GRID_BACKGROUND = 'DARK GREY'
LABEL_COLOR = 'LIGHT GREY'

# @@REMOVEME
DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")


class Gallery(object):
    def __init__(self, parent, image_cache, featured_series, running_series):
        self.parent = parent
        self.image_cache = image_cache
        self.featured_series = featured_series
        self.running_series = running_series

    def view(self):
        box = wx.BoxSizer(wx.VERTICAL)

        # Featured series

        label = self.sectionView("Featured Series", 1.25)

        thumbnails = [Thumbnail(self.parent, series.name, self.image_cache.get(
            series.poster_url).ConvertToBitmap()) for series in self.featured_series]
        grid = ThumbnailGrid(self.parent, thumbnails)

        box.Add(label, flag=wx.BOTTOM, border=20)
        box.Add(grid.view(), proportion=1, flag=wx.EXPAND)

        # Runnning series

        label = self.sectionView("Running Series", 1.25)

        thumbnails = [Thumbnail(self.parent, series.name, DEFAULT_IMAGE.ConvertToBitmap(
        )) for series in self.running_series]
        grid = ThumbnailGrid(self.parent, thumbnails)

        box.Add(label, flag=wx.BOTTOM, border=20)
        box.Add(grid.view(), proportion=1, flag=wx.EXPAND)

        return box

    def sectionView(self, text, scale):
        label = wx.StaticText(
            self.parent, wx.ID_ANY, label=text, style=wx.ALIGN_LEFT)
        font = label.GetFont()
        label.SetFont(font.MakeBold().Scale(scale))
        label.SetForegroundColour(LABEL_COLOR)
        return label


class Thumbnail(object):
    """
    Grid thumbail object
    """

    THUMBNAIL_SIZE = (190, 280)

    def __init__(self, parent, label, image, selected=False):
        self.parent = parent
        self.label = label
        self.image = image
        self.selected = selected

    def on_click(self, event):
        logging.debug(f"onClick {event.GetEventObject()}")
        # Toggle selection
        self.selected = not self.selected

    def view(self):
        box = wx.BoxSizer(wx.VERTICAL)
        # bitmap = wx.StaticBitmap(
        #     self.parent, wx.ID_ANY, self.image, size=self.THUMBNAIL_SIZE)
        button = wx.BitmapButton(self.parent, id=wx.ID_ANY, bitmap=wx.BitmapBundle(
            self.image), size=self.THUMBNAIL_SIZE)
        label = wx.StaticText(
            self.parent, wx.ID_ANY, label=self.label, style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_ELLIPSIZE_END | wx.SUNKEN_BORDER)
        label.SetForegroundColour(LABEL_COLOR)
        box.Add(button, flag=wx.BOTTOM | wx.ALIGN_CENTER, border=5)
        box.Add(label, flag=wx.EXPAND)
        button.Bind(wx.EVT_BUTTON, self.on_click)
        return box


class ThumbnailGrid(object):
    """
    A grid thumbnails, each showing an image and a label underneath
    """

    def __init__(self, parent, thumbnails):
        self.parent = parent
        self.thumbnails = thumbnails

    def view(self):
        # Four items per column
        grid = wx.GridSizer(4, 20, 10)
        for thumbnail in self.thumbnails:
            grid.Add(thumbnail.view())
        return grid
