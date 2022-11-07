import wx
#import logging
import views.theme as theme
from pubsub import pub

MSG_RELEASE_CLICKED = 'release.clicked'

class EpisodeView(object):
    """
    View holding a episode details
    """

    THUMBNAIL_SIZE = (400, 225)

    def __init__(self, image_cache, episode):
        self.image_cache = image_cache
        self.episode = episode

    def render(self, parent):
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Thimbail on the left 

        thumbnail_image = self.image_cache.get(self.episode.thumbnail_url)
        thumbnail = wx.StaticBitmap(
            parent, id=wx.ID_ANY, bitmap=thumbnail_image, size=self.THUMBNAIL_SIZE, style=wx.SUNKEN_BORDER)
        hbox.Add(thumbnail, flag=wx.ALL, border=20)

        # Details on the right

        vbox = wx.BoxSizer(wx.VERTICAL)

        #network_label = theme.make_label(parent, self.series.network.upper())
        title_label = theme.make_label(parent, self.episode.name, scale=2)
        releases_view = ReleaseListView(self.episode.releases)

        # @@TODO Add overview

        #vbox.Add(network_label, flag = wx.BOTTOM, border=10)
        vbox.Add(title_label, flag = wx.BOTTOM, border=10)
        vbox.Add(releases_view.render(parent))
        
        hbox.Add(vbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=20)
        return hbox


class ReleaseListView(object):
    """
    Show episode releases
    """

    def __init__(self, release_list):
        self.release_list = release_list

    # def on_click(self, event, info_hash):
    #     pub.sendMessage(MSG_RELEASE_CLICKED, info_hash=info_hash)

    def render(self, parent):
        box = wx.BoxSizer(wx.VERTICAL)
        for release in self.release_list:
            label = wx.StaticText(
                parent, id=wx.ID_ANY, label=release.original_name, style=wx.ST_ELLIPSIZE_END)
            label.SetForegroundColour(theme.LABEL_COLOR)
            #button.Bind(wx.EVT_BUTTON, lambda event: self.on_click(event, release.info_hash) )
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
        return box
