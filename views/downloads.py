import wx
#import logging
import views.theme as theme
from pubsub import pub

class DownloadsView(object):
    """
    List current transfers
    """

    def __init__(self, download_list):
        self.download_list = download_list

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)        
        for download in self.download_list:
            label = wx.StaticText(
                parent, id=wx.ID_ANY, label=f"{download.name}", style=wx.ST_ELLIPSIZE_END)
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
            
            gauge = wx.Gauge(parent, id=wx.ID_ANY, range=100)
            box.Add(gauge, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
            gauge.SetValue(download.progress)

            label = wx.StaticText(
                parent, id=wx.ID_ANY, label=f"{download.num_peers} peers, downloading at {download.dl_speed} / Uploading at {download.ul_speed}", style=wx.ST_ELLIPSIZE_END)
            box.Add(label, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=5)
            box.AddSpacer(10)
            #button = theme.make_button(parent, f"{episode.season_episode_id} {episode.name} (99)")
            # Capture episode_id while looping, see https://docs.python-guide.org/writing/gotchas/#late-binding-closures
            #button.Bind(wx.EVT_BUTTON, partial(self.on_click, episode.tvdb_id) )    
        return box