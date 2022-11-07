import wx
#import logging
import views.theme as theme
from pubsub import pub

# Messages 

MSG_SERIES_CLICKED = 'series.clicked'
DEFAULT_SERIES_IMAGE = wx.Image("./cache/default-poster.jpg", "image/jpeg")

class HomeView(object):
    def __init__(self, image_cache, featured_series, running_series):
        self.image_cache = image_cache
        self.featured_series = featured_series
        self.running_series = running_series

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)

        # Featured series

        label = theme.make_label(parent, "Featured Series", scale=1.25)
        box.Add(label, flag=wx.BOTTOM, border=20)

        thumbnails = [ThumbnailView(parent, series.tvdb_id, series.name, self.image_cache.get(
            series.poster_url, DEFAULT_SERIES_IMAGE).ConvertToBitmap()) for series in self.featured_series]
        grid = self.make_grid(parent, thumbnails)
        box.Add(grid, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=20)

        # Runnning series

        label = theme.make_label(parent, "Running Series", scale=1.25)
        box.Add(label, flag=wx.BOTTOM, border=20)

        thumbnails = [ThumbnailView(parent, series.tvdb_id, series.name, self.image_cache.get(
            series.poster_url, DEFAULT_SERIES_IMAGE).ConvertToBitmap()) for series in self.running_series]
        grid = self.make_grid(parent, thumbnails)
        box.Add(grid, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=20)

        return box

    def make_grid(self, parent, thumbnails) -> wx.GridSizer:
        # Four items per column
        grid = wx.GridSizer(4, 20, 10)
        for thumbnail in thumbnails:
            grid.Add(thumbnail.render(parent))
        return grid

class ThumbnailView(object):
    """
    Grid thumbail object
    """

    THUMBNAIL_SIZE = (190, 280)

    def __init__(self, parent, tvdb_id, label, image, selected=False):
        #self.parent = parent
        self.tvdb_id = tvdb_id
        self.label = label
        self.image = image
        self.selected = selected

    def on_click(self, event):
        # Toggle selection
        self.selected = not self.selected
        pub.sendMessage(MSG_SERIES_CLICKED, series_id=self.tvdb_id)

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)
        # bitmap = wx.StaticBitmap(
        #     self.parent, wx.ID_ANY, self.image, size=self.THUMBNAIL_SIZE)
        button = wx.BitmapButton(parent, id=wx.ID_ANY, bitmap=wx.BitmapBundle(
            self.image), size=self.THUMBNAIL_SIZE)
        label = wx.StaticText(
            parent, id=wx.ID_ANY, label=self.label, style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_ELLIPSIZE_END)
        label.SetForegroundColour(theme.LABEL_COLOR)
        box.Add(button, flag=wx.BOTTOM | wx.ALIGN_CENTER, border=10)
        box.Add(label, flag=wx.EXPAND)
        button.Bind(wx.EVT_BUTTON, self.on_click)
        return box