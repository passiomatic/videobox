import wx
#import logging
import views.theme as theme
from pubsub import pub

# Messages 


class SidebarView(object):
    def __init__(self, image_cache, featured_series):
        self.image_cache = image_cache
        self.featured_series = featured_series

    def render(self, parent) -> wx.BoxSizer:
        box = wx.BoxSizer(wx.VERTICAL)
        tree = wx.TreeCtrl(parent, wx.TR_HAS_BUTTONS)  

        root = tree.AddRoot('Something goes here')
        
        tree.SetPyData(root, ('key', 'value'))
        tree.AppendItem(root, 'Some node value')

        tree.Expand(root)
        box.Add(tree, wx.EXPAND)

        return box

