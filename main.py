import wx
#import requests

GRID_BACKGROUND = 'DARK GREY'
DEFAULT_IMAGE = wx.Image("./cache/default.jpg", "image/jpeg")


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
        self.panel.SetBackgroundColour(GRID_BACKGROUND)
        grid = ThumbnailGrid(self.panel, [])
        
        self.SetSize((1360, 1000))
        #self.ShowFullScreen(True)
        self.SetTitle('Simple menu')
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

    def OnQuit(self, e):
        self.Close()


class ThumbnailGrid():
    def __init__(self, parent, thumbnails):
        # Four items per column 
        self.grid = wx.GridSizer(4, 20, 10)                
        for index in range(12):
            bitmap = wx.StaticBitmap(
                parent, wx.ID_ANY, DEFAULT_IMAGE.ConvertToBitmap())
            self.grid.Add(bitmap, 1, wx.ALIGN_CENTER | wx.SHAPED)
        parent.SetSizer(self.grid)



class ImageCache():
    """
    Grab image from the local cache or fetch from given URL
    """

    def __init__(self, values=None):
        self.images = values if values else {}

    def get(self, url):
        try:
            # Schedule for fetching

            return self.images[url]
        except KeyError:
            return DEFAULT_IMAGE

    def add(self, url):
        self.images[url] = DEFAULT_IMAGE

    def set(self, url, image):
        self.images[url] = image


cache = ImageCache()


def main():

    cache.add(
        "https://www.thetvdb.com/banners/v4/series/419936/posters/6318d0ca3a8cd.jpg")
    cache.add(
        "https://www.thetvdb.com/banners/v4/series/401630/posters/614510da5fcb8.jpg")

    app = wx.App()
    ex = MainWindow(None)
    ex.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
