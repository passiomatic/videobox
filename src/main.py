import wx
import wx.adv
import logging
import configuration
import sync
import model
from cache import ImageCache
import views.home
import views.series
import views.episode
import views.nav
import views.downloads
import views.sidebar
import os
#import views.theme as theme
from pubsub import pub
import torrenter2  as torrenter
from dataclasses import dataclass

#import icons 

ID_MENU_SYNC = wx.NewIdRef()

@dataclass
class DownloadMock:
    name: str
    progress: int
    peers_count: int 
    download_speed: float 
    upload_speed: float

DOWNLOADS = [
    DownloadMock(name="Some release name", progress=70, peers_count=99, download_speed=3.5, upload_speed=0.9),
    # DownloadMock(name="Other release name", progress=0, peers_count=59, download_speed=9.5, upload_speed=5.9),
    # DownloadMock(name="A release name", progress=20, peers_count=9, download_speed=10.5, upload_speed=4)
]

@dataclass
class Icons:
    """
    All the icons used in the app
    """
    sync: wx.BitmapBundle

    @staticmethod
    def load(sizeDef=(16,16)):
        def get(filename):
            return wx.BitmapBundle.FromSVGFile(f"./images/{filename}.svg", sizeDef)

        return Icons(
            sync = get("arrows-clockwise")
        )

class MainWindow(wx.Frame):

    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        #self.selection = None
        
        self.icons = Icons.load()

        self.SetupMenuBar()

        self.main_panel = wx.Panel(self)
        self.nav_panel = wx.Panel(self.main_panel)
        self.downloads_panel = wx.Panel(self.main_panel)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        toolbar = self.SetupToolBar(self.main_panel)
        main_sizer.Add(toolbar, proportion=0, flag=wx.EXPAND)

        # sidebar_view = views.sidebar.SidebarView(self.app.image_cache, [])
        # main_sizer.Add(sidebar_view.render(self.main_panel), flag=wx.EXPAND | wx.ALL, border=10)

        featured_series = model.get_featured_series(interval=2)[:12]
        running_series = model.get_updated_series(interval=2)[:12]            
        home_view = views.home.HomeView(self.app.image_cache, featured_series, running_series)                
        self.home_nav = views.nav.HomeNavView(home_view)
        self.UpdateNavPanel()
        main_sizer.Add(self.nav_panel, proportion=1, flag=wx.EXPAND)

        # Downloads 
        self.UpdateDownloadsPanel()
        main_sizer.Add(self.downloads_panel, flag=wx.EXPAND)

        self.main_panel.SetSizer(main_sizer)

        screen_width, screen_height = wx.GetDisplaySize()
        win_width = min(screen_width, 1680)
        win_height = min(screen_height, 800)
        self.SetSize((win_width, win_height))
        # self.ShowFullScreen(True)
        self.Centre()

        # Listen to various events from views
        pub.subscribe(self.OnSeriesClicked, views.home.MSG_SERIES_CLICKED)
        pub.subscribe(self.OnEpisodeClicked, views.series.MSG_EPISODE_CLICKED)
        pub.subscribe(self.OnReleaseClicked, views.episode.MSG_RELEASE_CLICKED)        
        pub.subscribe(self.OnBackClicked, views.nav.MSG_BACK_CLICKED)

    def OnSeriesClicked(self, series_id):
        series = model.get_series(series_id)
        current_view = views.series.SeriesView(self.app.image_cache, series)
        self.home_nav.add_view(current_view)
        self.UpdateNavPanel()

    def OnEpisodeClicked(self, episode_id):
        episode = model.get_episode(episode_id)    
        current_view = views.episode.EpisodeView(self.app.image_cache, episode)
        self.home_nav.add_view(current_view)
        self.UpdateNavPanel()

    def OnReleaseClicked(self, info_hash):
        release = model.get_release(info_hash)
        self.app.torrenter.add_torrent(self.app.download_dir, release.magnet_uri)
        self.UpdateNavPanel()

    def OnBackClicked(self):
        self.home_nav.back()
        self.UpdateNavPanel()

    def UpdateNavPanel(self):
         # Cleanup dangling children
        self.nav_panel.DestroyChildren() 
        nav_sizer = self.home_nav.render(self.nav_panel)
        self.nav_panel.SetSizer(nav_sizer)        
        self.nav_panel.Layout()   

    def UpdateDownloadsPanel(self):
         # Cleanup dangling children
        self.downloads_panel.DestroyChildren() 
        if self.app.torrenter.torrents_status:
            downloads_view = views.downloads.DownloadsView(self.app.torrenter.torrents_status)
            #downloads_view = views.downloads.DownloadsView(DOWNLOADS)
            downloads_sizer = downloads_view.render(self.downloads_panel)
            # @@TODO force calc with new panel contents
            self.downloads_panel.SetSizer(downloads_sizer)
        self.downloads_panel.Layout()
        #self.downloads_panel.Update()


    def SetupToolBar(self, parent):
        toolbar = wx.ToolBar(parent, style=wx.TB_TEXT)
        toolbar.AddTool(ID_MENU_SYNC, label="Sync", bitmap=self.icons.sync, shortHelp="Synchronize library with latest shows")
        toolbar.Realize()
        return toolbar

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
        # During developments prefer using local directories
        if configuration.USE_LOCAL_DIRS:
            app_dir = os.getcwd()
            self.cache_dir = os.path.join(app_dir, "Cache")
            self.download_dir = os.path.join(app_dir, "Transfers")
        else:
            paths = wx.StandardPaths.Get()
            app_dir = paths.UserLocalDataDir
            self.cache_dir = os.path.join(paths.UserLocalDataDir, "Cache")
            self.download_dir = os.path.join(paths.AppDocumentsDir, "Transfers")

        os.makedirs(self.cache_dir, exist_ok=True)
        logging.info(f"Cache dir is {self.cache_dir}")
        
        os.makedirs(self.download_dir, exist_ok=True)
        logging.info(f"Download dir is {self.download_dir}")

        model.connect(app_dir, shouldSetup=True)

        self.torrenter = torrenter.Torrenter(update_callback=self.OnTorrentUpdate)
        self.image_cache = ImageCache(self.cache_dir)

        self.sync_worker = sync.SyncWorker(progress_callback=self.OnSyncProgress, done_callback=self.SyncEnded)
        self.frame = MainWindow(self, parent=None, id=wx.ID_ANY, title="Videobox")
        
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUI)

        self.frame.Show()
        return True

    def OnExit(self):
        # Wait a bit for Torrenter instance to shutdown
        self.torrenter.keep_running = False
        self.torrenter.join(5)
        logging.debug("Exiting app")
        return super().OnExit()

    def OnUpdateUI(self, event):        
        # Have a chance to update various UI elements
        id = event.GetId()

        if id==ID_MENU_SYNC:
            event.Enable(not self.IsSyncing())
        else:
            pass

    def OnQuitClicked(self, event):
        self.frame.Close()

    def OnSyncClicked(self, event):
        self.SyncData()

    def OnSyncProgress(self, message, percent=None):
        #logging.info(f"{message} {percent}")
        pass

    def SyncData(self):
        if self.IsSyncing():
            logging.debug("Synchronization is running, ignored request")
        else:
            self.sync_worker.start()
    
    def SyncEnded(self, result):
        message = wx.adv.NotificationMessage("Sync", result)
        message.Show()

    def IsSyncing(self):
        return self.sync_worker.is_alive()

    def OnTorrentUpdate(self, handle):
        status = self.torrenter.get_torrent_status(handle)
        self.frame.UpdateDownloadsPanel()
        logging.debug(f"{status}")


def main():

    logging.basicConfig(level=configuration.log_level)
    for module in ['peewee', 'requests', 'urllib3', 'PIL']:
        # Set higher log level for deps
        logging.getLogger(module).setLevel(logging.WARN)

    app = VideoboxApp()
    #app.SetAppName(configuration.APP_NAME)
    app.MainLoop()


if __name__ == '__main__':
    main()
