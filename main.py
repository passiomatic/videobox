import wx
from wx.lib.scrolledpanel import ScrolledPanel
import logging
import configuration
import sync
import model
from cache import ImageCache
import views.home
import views.series
import views.nav
import os
import views.theme as theme
from pubsub import pub

DEFAULT_IMAGE = wx.Image("./cache/sample-poster.jpg", "image/jpeg")

ID_MENU_SYNC = wx.NewIdRef()

class MainWindow(wx.Frame):

    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        #self.selection = None
        
        self.SetupMenuBar()

        self.top_panel = wx.Panel(self)
        
        featured_series = model.get_featured_series(interval=2)[:8]
        running_series = model.get_updated_series(interval=2)[:8]            
        current_view = views.home.HomeView(self.app.image_cache, featured_series, running_series)                
        
        self.home_nav = views.nav.HomeNavView(current_view)
        nav_sizer = self.home_nav.render(self.top_panel)
        self.top_panel.SetSizer(nav_sizer)

        screen_width, screen_height = wx.GetDisplaySize()
        win_width = min(screen_width, 1680)
        win_height = min(screen_height, 800)
        self.SetSize((win_width, win_height))
        # self.ShowFullScreen(True)
        self.Centre()

        # Listen to various events from views
        pub.subscribe(self.OnSeriesClicked, views.home.MSG_SERIES_CLICKED)
        pub.subscribe(self.OnEpisodeClicked, views.series.MSG_EPISODE_CLICKED)

    def OnSeriesClicked(self, series_id):
        series = model.get_series(series_id)
        current_view = views.series.SeriesView(self.app.image_cache, series)
        self.home_nav.addView(current_view)
        nav_sizer = self.home_nav.render(self.top_panel)
        self.top_panel.SetSizer(nav_sizer)
        self.top_panel.Layout()

    def OnEpisodeClicked(self, episode_id):
        episode = model.get_episode(episode_id)    
        current_view = views.episode.EpisodeView(self.app.image_cache, episode)
        self.home_nav.addView(current_view)
        nav_sizer = self.home_nav.render(self.top_panel)
        self.top_panel.SetSizer(nav_sizer)
        self.top_panel.Layout()

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
