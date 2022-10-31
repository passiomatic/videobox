import wx
from wx.lib.scrolledpanel import ScrolledPanel
#import requests
import logging
import configuration
import sync
import model
from cache import ImageCache

GRID_BACKGROUND = 'DARK GREY'
LABEL_COLOR = 'LIGHT GREY'

DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")
THUMBNAIL_SIZE = (680, 1000)

class MainWindow(wx.Frame):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.featured_series = model.get_featured_series(interval=2)

        self.SetupMenuBar()
        self.GalleryView()


    def GalleryView(self):
        """
        Main view for the app
        """
        #self.panel = wx.Panel(self)
        self.panel = ScrolledPanel(self, wx.ID_ANY)

        self.panel.Bind(wx.EVT_PAINT, self.OnPaint)
        # self.panel.SetBackgroundColour(GRID_BACKGROUND)

        box = wx.BoxSizer(wx.VERTICAL)

        label = titleLabel(self.panel, "Featured Series", 1.25)
        grid = ThumbnailGrid(self.panel, self.featured_series[:16])

        box.Add(label, flag=wx.BOTTOM, border=20)
        box.Add(grid, proportion=1, flag=wx.EXPAND) # Fit to container

        self.panel.SetSizer(box)
        self.panel.SetupScrolling()

        screen_width, screen_height = wx.GetDisplaySize()
        win_width = min(screen_width, 1680)
        win_height = min(screen_height, 800)
        self.SetSize((win_width, win_height))
        # self.ShowFullScreen(True)
        self.Centre()

    def SetupMenuBar(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        videoMenu = wx.Menu()
        libraryMenu = wx.Menu()
        fileItem = fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
        menubar.Append(fileMenu, '&File')
        menubar.Append(videoMenu, '&Video')
        menubar.Append(libraryMenu, '&Library')
        syncItem = libraryMenu.Append(wx.ID_ANY, 'Sync', 'Synchronize library with latest shows')
        self.Bind(wx.EVT_MENU, self.OnQuit, fileItem)
        self.Bind(wx.EVT_MENU, self.OnSync, syncItem)
        self.SetMenuBar(menubar)

    def OnQuit(self, event):
        self.Close()

    def OnSync(self, event):
        # TODO Check if syncing already
        syncer = sync.SyncWorker()
        syncer.start()

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
        for thumbnail in thumbnails:
            box = wx.BoxSizer(wx.VERTICAL)
            # TODO Show poster
            bitmap = wx.StaticBitmap(
                parent, wx.ID_ANY, DEFAULT_IMAGE.ConvertToBitmap(), size=(190, 280), style=wx.SUNKEN_BORDER)
            label = wx.StaticText(
                parent, wx.ID_ANY, label=thumbnail.name, style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_ELLIPSIZE_END | wx.SUNKEN_BORDER)
            label.SetForegroundColour(LABEL_COLOR)
            box.Add(bitmap, flag=wx.BOTTOM | wx.ALIGN_CENTER, border=5)
            box.Add(label, flag=wx.EXPAND)
            self.Add(box)

            #parent.Bind(wx.EVT_BUTTON, parent.OnThumbnailClick, bitmap)


class MyDataStructure(object):
    """
    Placeholder data structure
    """

    def __init__(self):
        pass

    def load_data(self):
        return []

class VideoboxApp(wx.App):
    def OnInit(self):
        self.syncWorker = sync.SyncWorker()
        #data = model.get_featured_series(interval=2)
        frame = MainWindow(None, wx.ID_ANY, "Videobox")
        data = MyDataStructure()
        #self.controller = VideoboxController(frame, data)

        # eventually...
        # self.controller1 = DataViewController(frame, data)
        # self.controller2 = AnimationController(frame)
        # etc.
        
        #self.SetTopWindow(frame)
        frame.Show()
        return True

    def OnSyncClicked(self, event):
        self.SyncData()

    def SyncData(self):
        if self.syncWorker.is_alive():
            logging.debug("Synchronization is running, ignored request")
        else:
            self.syncWorker.start()

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

    model.connect(shouldSetup=True)

    app = VideoboxApp()
    app.MainLoop()


if __name__ == '__main__':
    main()
