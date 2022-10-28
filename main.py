import wx
#import requests
import logging
import configuration
import sync
import model
from cache import ImageCache

GRID_BACKGROUND = 'DARK GREY'
LABEL_COLOR = 'LIGHT GREY'

DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")


class MainWindow(wx.Frame):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.SetupMenuBar()
        self.GalleryView()

    def GalleryView(self):
        """
        Main view for the app
        """
        self.panel = wx.Panel(self)
        self.panel.Bind(wx.EVT_PAINT, self.OnPaint)
        # self.panel.SetBackgroundColour(GRID_BACKGROUND)

        box = wx.BoxSizer(wx.VERTICAL)

        label = titleLabel(self.panel, "Featured Series", 1.5)
        grid = ThumbnailGrid(self.panel, [])

        box.Add(label, proportion=1, flag=wx.BOTTOM, border=20)
        box.Add(grid, proportion=1)

        self.panel.SetSizer(box)

        self.SetSize((1360, 1000))
        # self.ShowFullScreen(True)
        #self.SetTitle('Simple menu')
        self.Centre()

    def SetupMenuBar(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        videoMenu = wx.Menu()
        fileItem = fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
        menubar.Append(fileMenu, '&File')
        menubar.Append(videoMenu, '&Video')
        self.Bind(wx.EVT_MENU, self.OnQuit, fileItem)
        self.SetMenuBar(menubar)

    def OnQuit(self, event):
        self.Close()

    def OnThumbnailClick(self, event):
        logging.DEBUG(f"OnThumbnailClick {event}")

    def OnPaint(self, event):
        # establish the painting canvas
        dc = wx.PaintDC(self.panel)
        x = 0
        y = 0
        w, h = self.GetSize()
        dc.GradientFillLinear((x, y, w, h), GRID_BACKGROUND,
                              'black', nDirection=wx.BOTTOM)


def titleLabel(parent, text, scale):
    label = wx.StaticText(
        parent, wx.ID_ANY, label=text, style=wx.ALIGN_LEFT)
    font = label.GetFont()
    label.SetFont(font.MakeBold().Scale(scale))
    label.SetForegroundColour(LABEL_COLOR)
    return label


class ThumbnailGrid(wx.GridSizer):
    def __init__(self, parent, thumbnails):
        # Four items per column
        super(wx.GridSizer, self).__init__(4, 20, 10)
        for index in range(12):
            box = wx.BoxSizer(wx.VERTICAL)
            bitmap = wx.StaticBitmap(
                parent, wx.ID_ANY, DEFAULT_IMAGE.ConvertToBitmap(), style=wx.SUNKEN_BORDER)
            label = wx.StaticText(
                parent, wx.ID_ANY, label="Some title", style=wx.ALIGN_CENTRE_HORIZONTAL)
            label.SetForegroundColour(LABEL_COLOR)
            box.Add(bitmap, proportion=1, flag=wx.BOTTOM, border=5)
            box.Add(label, proportion=0, flag=wx.EXPAND)
            self.Add(box, proportion=1, flag=wx.ALIGN_CENTER | wx.SHAPED)

            #parent.Bind(wx.EVT_BUTTON, parent.OnThumbnailClick, bitmap)


class MyDataStructure(object):
    """
    Placeholder data structure
    """

    def __init__(self):
        pass

    def load_data(self):
        return []


class AppController(wx.EvtHandler):
    def __init__(self, frame, data):
        self.frame = frame
        self.data = data

        # create child controls
        # self.button = wx.Button(self.frame, -1, "Sync")

        # # bind events
        # self.button.Bind(wx.EVT_BUTTON, self.OnSyncClicked)

    def OnSyncClicked(self, event):
        self.SyncData()

    def SyncData(self):
        # self.data.load_data()
        # populate wx.Frame controls with data
        pass


class VideoboxApp(wx.App):
    def OnInit(self):
        data = model.get_featured_series(7)
        frame = MainWindow(None, wx.ID_ANY, "Videobox")
        #data = MyDataStructure()
        self.controller = AppController(frame, data)

        # eventually...
        # self.controller1 = DataViewController(frame, data)
        # self.controller2 = AnimationController(frame)
        # etc.

        frame.Show()
        return True


def main():

    logging.basicConfig(level=configuration.log_level)
    for module in ['peewee', 'requests', 'urllib3']:
        # Set higher log level for deps
        logging.getLogger(module).setLevel(logging.WARN)

    cache = ImageCache(DEFAULT_IMAGE)

    cache.add(
        "https://www.thetvdb.com/banners/v4/series/419936/posters/6318d0ca3a8cd.jpg")
    cache.add(
        "https://www.thetvdb.com/banners/v4/series/401630/posters/614510da5fcb8.jpg")

    model.connect(shouldSetup=False)

    # syncer = sync.Syncer()
    # syncer.start()
    # logging.debug("Back to main thread")

    app = VideoboxApp()
    app.MainLoop()


if __name__ == '__main__':
    main()
