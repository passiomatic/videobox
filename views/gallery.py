import wx
import logging
import views.theme as theme

class GalleryView(object):
    def __init__(self, parent, image_cache, featured_series, running_series):
        self.parent = parent
        self.image_cache = image_cache
        self.featured_series = featured_series
        self.running_series = running_series

    def view(self):
        box = wx.BoxSizer(wx.VERTICAL)

        # Featured series

        label = theme.make_label(self.parent, "Featured Series", scale=1.25)

        thumbnails = [ThumbnailView(self.parent, series.name, self.image_cache.get(
            series.poster_url).ConvertToBitmap()) for series in self.featured_series]
        grid = ThumbnailGridView(self.parent, thumbnails)

        box.Add(label, flag=wx.BOTTOM, border=20)
        box.Add(grid.view(), proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=20)

        # Runnning series

        label = theme.make_label(self.parent, "Running Series", scale=1.25)

        thumbnails = [ThumbnailView(self.parent, series.name, self.image_cache.get(
            series.poster_url).ConvertToBitmap()) for series in self.running_series]
        grid = ThumbnailGridView(self.parent, thumbnails)

        box.Add(label, flag=wx.BOTTOM, border=20)
        box.Add(grid.view(), proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=20)

        return box


class ThumbnailView(object):
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
            self.parent, id=wx.ID_ANY, label=self.label, style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_ELLIPSIZE_END)
        label.SetForegroundColour(theme.LABEL_COLOR)
        box.Add(button, flag=wx.BOTTOM | wx.ALIGN_CENTER, border=10)
        box.Add(label, flag=wx.EXPAND)
        button.Bind(wx.EVT_BUTTON, self.on_click)
        return box


class ThumbnailGridView(object):
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
