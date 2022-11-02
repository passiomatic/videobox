import wx
from wx.lib.scrolledpanel import ScrolledPanel
#import requests
import logging
import configuration
import sync
import model
from cache import ImageCache
import views.gallery

GRID_BACKGROUND = 'DARK GREY'
LABEL_COLOR = 'LIGHT GREY'

DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")

ID_MENU_SYNC = wx.NewIdRef()

class MainWindow(wx.Frame):

    def __init__(self, controller, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.controller = controller

        self.SetupMenuBar()
        self.GalleryView()

    def GalleryView(self):
        """
        Main view for the app
        """
        #self.panel = wx.Panel(self)
        self.panel = ScrolledPanel(self, wx.ID_ANY)

        featured_series = model.get_featured_series(interval=2)[:8]
        running_series = model.get_updated_series(interval=2)[:8]
        gallery = views.gallery.Gallery(self.panel, featured_series, running_series)

        self.panel.SetSizer(gallery.view())
        self.panel.SetupScrolling(scroll_x=False)

        screen_width, screen_height = wx.GetDisplaySize()
        win_width = min(screen_width, 1680)
        win_height = min(screen_height, 800)
        self.SetSize((win_width, win_height))
        # self.ShowFullScreen(True)
        self.panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Centre()

    def SetupMenuBar(self):
        menubar = wx.MenuBar()
        #fileMenu = wx.Menu()
        videoMenu = wx.Menu()
        libraryMenu = wx.Menu()
        #fileItem = fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
        #menubar.Append(fileMenu, '&File')
        menubar.Append(videoMenu, '&Video')
        menubar.Append(libraryMenu, '&Library')
        syncItem = libraryMenu.Append(ID_MENU_SYNC, 'Sync', 'Synchronize library with latest shows')
        #self.Bind(wx.EVT_MENU, self.controller.OnQuitClicked, fileItem)
        self.Bind(wx.EVT_MENU, self.controller.OnSyncClicked, id=ID_MENU_SYNC)
        self.SetMenuBar(menubar)

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
          
class VideoboxApp(wx.App):
    def OnInit(self):
        self.imageCache = ImageCache(DEFAULT_IMAGE)

        # cache.add(
        #     "https://www.thetvdb.com/banners/v4/series/419936/posters/6318d0ca3a8cd.jpg")
        # cache.add(
        #     "https://www.thetvdb.com/banners/v4/series/401630/posters/614510da5fcb8.jpg")

        self.syncWorker = sync.SyncWorker(done_callback=self.UpdateUI)
        self.frame = MainWindow(self, parent=None, id=wx.ID_ANY, title="Videobox")
        #self.controller = VideoboxController(frame, data)
        
        # eventually...
        # self.controller1 = DataViewController(frame, data)
        # self.controller2 = AnimationController(frame)
        # etc.
        
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

        self.frame.Show()
        return True

    # ----------
    # Events
    # ----------

    def OnUpdateUI(self, event):        
        id = event.GetId()

        if id==ID_MENU_SYNC:
            event.Enable(not self.syncWorker.is_alive())
        else:
            pass

    def OnQuitClicked(self, event):
        self.frame.Close()

    def OnSyncClicked(self, event):
        self.SyncData()

    def SyncData(self):
        if self.syncWorker.is_alive():
            logging.debug("Synchronization is running, ignored request")
        else:
            self.syncWorker.start()

    def UpdateUI(self):
        self.frame.Layout()
        #self.frame.Refresh()
        self.frame.Update()


def main():

    logging.basicConfig(level=configuration.log_level)
    for module in ['peewee', 'requests', 'urllib3']:
        # Set higher log level for deps
        logging.getLogger(module).setLevel(logging.WARN)

    model.connect(shouldSetup=True)

    app = VideoboxApp()
    app.MainLoop()


if __name__ == '__main__':
    main()
