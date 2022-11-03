import wx
from wx.lib.scrolledpanel import ScrolledPanel
import logging
import configuration
import sync
import model
from cache import ImageCache
import views.gallery
import views.series
import os
import views.theme as theme
from pubsub import pub

DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")

ID_MENU_SYNC = wx.NewIdRef()

class MainWindow(wx.Frame):

    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        self.selection = None

        self.SetupMenuBar()
        self.main_panel = MainPanel(self, self.app, self.selection)

        screen_width, screen_height = wx.GetDisplaySize()
        win_width = min(screen_width, 1680)
        win_height = min(screen_height, 800)
        self.SetSize((win_width, win_height))
        # self.ShowFullScreen(True)
        self.Centre()

        # Listen to various events from views
        pub.subscribe(self.OnSeriesClicked, views.gallery.MSG_SERIES_CLICKED)

    def OnSeriesClicked(self, series_id):
        self.selection = model.get_series(series_id)
        self.main_panel.Selection = self.selection
        self.Update()   

    def SetupMenuBar(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        videoMenu = wx.Menu()
        libraryMenu = wx.Menu()
        fileItem = fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
        menubar.Append(fileMenu, '&File')
        menubar.Append(videoMenu, '&Video')
        menubar.Append(libraryMenu, '&Library')
        syncItem = libraryMenu.Append(ID_MENU_SYNC, 'Sync', 'Synchronize library with latest shows')
        self.Bind(wx.EVT_MENU, self.app.OnQuitClicked, fileItem)
        self.Bind(wx.EVT_MENU, self.app.OnSyncClicked, id=ID_MENU_SYNC)
        self.SetMenuBar(menubar)

class MainPanel(ScrolledPanel):

    def __init__(self, parent, app, selection):
        super().__init__(parent)
        self.app = app
        #self.parent = parent
        self._selection = selection        
        self.UpdateContent()
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def UpdateContent(self):
        if isinstance(self.Selection, model.Series):
            # Series view 
            current_view = views.series.SeriesView(self, self.app.image_cache, self.Selection)
        elif isinstance(self.Selection, model.Episode):
            # Episode view
            # @@TODO 
            pass
        else:
            # Default view
            featured_series = model.get_featured_series(interval=2)[:8]
            running_series = model.get_updated_series(interval=2)[:8]            
            current_view = views.gallery.GalleryView(self, self.app.image_cache, featured_series, running_series)
        
        # @@TODO Hide panel with effect instead     
        self.DestroyChildren()
        self.SetSizer(current_view.view())
        self.SetupScrolling(scroll_x=False)     

    @property
    def Selection(self):
        return self._selection

    @Selection.setter
    def Selection(self, value):
        self._selection = value
        self.UpdateContent()  

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        dc.GradientFillLinear((0, 0, w, h), theme.GRID_BACKGROUND_START,
                              theme.GRID_BACKGROUND_STOP, nDirection=wx.BOTTOM)


class VideoboxApp(wx.App):
    def OnInit(self):
        app_dir = os.getcwd()
        
        # Cache directory
        cache_dir = os.path.join(app_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        self.image_cache = ImageCache(cache_dir, DEFAULT_IMAGE)

        self.sync_worker = sync.SyncWorker(done_callback=None)
        self.frame = MainWindow(self, parent=None, id=wx.ID_ANY, title="Videobox")
        
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

        self.frame.Show()
        return True

    # ----------
    # Event handlers
    # ----------

    def OnUpdateUI(self, event):        
        # Have a chance to update variosu UI elements
        id = event.GetId()

        if id==ID_MENU_SYNC:
            event.Enable(not self.sync_worker.is_alive())
        else:
            pass

    def OnQuitClicked(self, event):
        self.frame.Close()

    def OnSyncClicked(self, event):
        self.SyncData()

    def SyncData(self):
        if self.sync_worker.is_alive():
            logging.debug("Synchronization is running, ignored request")
        else:
            self.sync_worker.start()

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
