import wx
#import logging
import views.theme as theme
from pubsub import pub
import model 
from functools import partial

MSG_EPISODE_CLICKED = 'episode.clicked'
DEFAULT_SERIES_IMAGE = wx.Image("./cache/default-poster.jpg", "image/jpeg")

class SeriesView(object):
    """
    Series details
    """

    THUMBNAIL_SIZE = (190, 280)

    def __init__(self, image_cache, series):
        self.image_cache = image_cache
        self.series = series

    def render(self, parent) -> wx.BoxSizer:
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Poster on the left 

        poster_image = self.image_cache.get(self.series.poster_url, DEFAULT_SERIES_IMAGE)
        poster = wx.StaticBitmap(
            parent, id=wx.ID_ANY, bitmap=poster_image, size=self.THUMBNAIL_SIZE, style=wx.SUNKEN_BORDER)
        hbox.Add(poster, flag=wx.ALL, border=20)

        # Details on the right

        vbox = wx.BoxSizer(wx.VERTICAL)

        network_label = theme.make_label(parent, self.series.network.upper())
        title_label = theme.make_label(parent, self.series.name, scale=2)
        episodes_view = EpisodeListView(self.series.episodes)

        vbox.Add(network_label, flag = wx.BOTTOM, border=10)
        vbox.Add(title_label, flag = wx.BOTTOM, border=10)
        vbox.Add(episodes_view.render(parent))
        
        hbox.Add(vbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=20)
        return hbox


class EpisodeListView(object):
    """
    Series episodes
    """

    def __init__(self, episode_list):
        self.episode_list = episode_list

    def on_click(self, episode_id, event):
        pub.sendMessage(MSG_EPISODE_CLICKED, episode_id=episode_id)

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)        
        # @@TODO Group by season
        for episode in self.episode_list.order_by(model.Episode.number, model.Episode.season.desc()):
            # label = wx.StaticText(
            #     parent, id=wx.ID_ANY, label=f"{episode.season_episode_id} {episode.name} (99)", style=wx.ST_ELLIPSIZE_END)
            # label.SetForegroundColour(theme.LABEL_COLOR)
            # box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
            button = theme.make_button(parent, f"{episode.season_episode_id} {episode.name} (99)")
            # Capture episode_id while looping, see https://docs.python-guide.org/writing/gotchas/#late-binding-closures
            button.Bind(wx.EVT_BUTTON, partial(self.on_click, episode.tvdb_id) )
            box.Add(button, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
        return box
