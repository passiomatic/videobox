import wx
#import logging
import views.theme as theme
from pubsub import pub
from functools import partial
import model  

MSG_RELEASE_CLICKED = 'release.clicked'
DEFAULT_EPISODE_IMAGE = wx.Image("./cache/default-thumbnail.jpg", "image/jpeg")

class EpisodeView(object):
    """
    Episode details
    """

    THUMBNAIL_SIZE = (400, 225)

    def __init__(self, image_cache, episode):
        self.image_cache = image_cache
        self.episode = episode

    def render(self, parent):
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Thumbnail on the left 

        thumbnail_image = self.image_cache.get(self.episode.thumbnail_url, DEFAULT_EPISODE_IMAGE)
        thumbnail = wx.StaticBitmap(
            parent, id=wx.ID_ANY, bitmap=thumbnail_image, size=self.THUMBNAIL_SIZE, style=wx.SUNKEN_BORDER)
        hbox.Add(thumbnail, flag=wx.ALL, border=20)

        # Details on the right

        vbox = wx.BoxSizer(wx.VERTICAL)

        title_label = theme.make_label(parent, self.episode.name, color=theme.LABEL_COLOR, scale=2)
        releases_view = ReleaseListView(self.episode.releases)
        overview_text = wx.StaticText(
            parent, wx.ID_ANY, label=self.episode.overview, style=wx.ALIGN_LEFT | wx.ST_ELLIPSIZE_END)
        overview_text.SetForegroundColour(theme.LABEL_COLOR)

        vbox.Add(title_label, flag = wx.BOTTOM, border=10)
        vbox.Add(overview_text, flag = wx.BOTTOM, border=10)
        vbox.Add(releases_view.render(parent))
        
        hbox.Add(vbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=20)
        return hbox


class ReleaseListView(object):
    """
    Episode releases
    """

    def __init__(self, release_list):
        self.release_list = release_list

    def on_click(self, info_hash, event):
        pub.sendMessage(MSG_RELEASE_CLICKED, info_hash=info_hash)

    def render(self, parent):
        box = wx.BoxSizer(wx.VERTICAL)
        for release in self.release_list.order_by(model.Release.seeds.desc()):
            # label = wx.StaticText(
            #     parent, id=wx.ID_ANY, label=release.original_name, style=wx.ST_ELLIPSIZE_END)
            # label.SetForegroundColour(theme.LABEL_COLOR)
            button = theme.make_button(parent, f"{release.original_name} ({release.seeds})")
            # Capture info_hash while looping, see https://docs.python-guide.org/writing/gotchas/#late-binding-closures
            button.Bind(wx.EVT_BUTTON, partial(self.on_click, release.info_hash) )
            box.Add(button, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
        return box
