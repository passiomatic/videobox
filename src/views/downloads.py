import wx
#import logging
import views.theme as theme
from pubsub import pub

class DownloadsView(object):
    """
    List current transfers
    """

    def __init__(self, status_list):
        self.status_list = status_list

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)  
        title_label = theme.make_title(parent, "Downloads")
        box.Add(title_label, flag=wx.EXPAND | wx.BOTTOM, border=5)
        for download in self.status_list:
            label = wx.StaticText(
                parent, id=wx.ID_ANY, label=f"{download.name}", style=wx.ST_ELLIPSIZE_END)
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=0)
            
            gauge = wx.Gauge(parent, id=wx.ID_ANY, range=100)
            box.Add(gauge, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=0)
            gauge.SetValue(download.progress)

            label = wx.StaticText(
                parent, 
                label=str(download), 
                style=wx.ST_ELLIPSIZE_END)
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=0)
            box.AddSpacer(10)
            #button = theme.make_button(parent, f"{episode.season_episode_id} {episode.name} (99)")
            # Capture episode_id while looping, see https://docs.python-guide.org/writing/gotchas/#late-binding-closures
            #button.Bind(wx.EVT_BUTTON, partial(self.on_click, episode.tvdb_id) )    
        return box

    # def update(self):
    #     pass