import wx
#import logging
import views.theme as theme
from pubsub import pub
import configuration

# Messages 

# Views

class SidebarView(object):
    def __init__(self, image_cache, featured_series):
        self.image_cache = image_cache
        self.featured_series = featured_series

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)

        # TODO: Use wx.CollapsiblePane instead

        # Series        
        
        series_tree = wx.TreeCtrl(parent, wx.TR_HAS_BUTTONS)  
        root = series_tree.AddRoot('Series')
        
        #series_tree.SetPyData(root, ('key', 'value'))
        series_tree.AppendItem(root, 'Featured')

        #series_tree.SetPyData(root, ('key', 'value'))
        series_tree.AppendItem(root, 'Running')

        series_tree.Expand(root)
        box.Add(series_tree, proportion=1, flag=wx.EXPAND)

        # Tags

        tags_tree = wx.TreeCtrl(parent, wx.TR_HAS_BUTTONS)  
        root = tags_tree.AddRoot('Tags')

        for tag, translation in configuration.TAGS.items():
            #tags_tree.SetPyData(root, ('key', 'value'))
            tags_tree.AppendItem(root, translation)

        tags_tree.Expand(root)
        box.Add(tags_tree, proportion=1, flag=wx.EXPAND)

        return box

