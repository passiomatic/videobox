import wx
#import logging
import views.theme as theme


class SeriesView(object):
    """
    View holding a series' details
    """

    THUMBNAIL_SIZE = (190, 280)

    def __init__(self, parent, image_cache, series):
        self.parent = parent
        self.image_cache = image_cache
        self.series = series

    def view(self):
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Poster on the left 

        poster_image = self.image_cache.get(self.series.poster_url)
        poster = wx.StaticBitmap(
            self.parent, id=wx.ID_ANY, bitmap=poster_image, size=self.THUMBNAIL_SIZE, style=wx.SUNKEN_BORDER)
        hbox.Add(poster, flag=wx.ALL, border=20)

        # Details on the right

        vbox = wx.BoxSizer(wx.VERTICAL)

        network_label = theme.make_label(self.parent, self.series.network.upper())
        title_label = theme.make_label(self.parent, self.series.name, scale=2)
        episodes_view = EpisodeListView(self.parent, self.series.episodes)

        vbox.Add(network_label, flag = wx.BOTTOM, border=10)
        vbox.Add(title_label, flag = wx.BOTTOM, border=10)
        vbox.Add(episodes_view.view())
        
        hbox.Add(vbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=20)
        return hbox


class EpisodeListView(object):
    """
    Show series' episodes
    """

    def __init__(self, parent, episode_list):
        self.parent = parent
        self.episode_list = episode_list

    # def on_click(self, event):
    #     logging.debug(f"onClick {event.GetEventObject()}")

    def view(self):
        # @@TODO Group by season
        box = wx.BoxSizer(wx.VERTICAL)
        for episode in self.episode_list:
            label = wx.StaticText(
                self.parent, id=wx.ID_ANY, label=f"{episode.season_episode_id} {episode.name}", style=wx.ST_ELLIPSIZE_END)
            label.SetForegroundColour(theme.LABEL_COLOR)
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
        return box