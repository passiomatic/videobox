
import wx
import logging
import views.theme as theme
#from pubsub import pub
from wx.lib.scrolledpanel import ScrolledPanel


class HomeNavView(object):
    """
    Show one panel only
    """

    def __init__(self, view):
        # At least one view must be present
        self.views = [view]

    def addView(self, view):
        self.views.append(view)

    def back(self):
        if len(self.views) > 1:
            view = self.views.pop()
            #panel.HideWithEffect(wx.SHOW_EFFECT_SLIDE_TO_RIGHT, timeout=300)
        else:
            logging.warn("Cannot go back when in home, command ignored")
                        
    def view(self, parent) -> wx.BoxSizer:
        top_sizer = wx.BoxSizer()
        for index, view in enumerate(reversed(self.views)):
            panel = HomeNavPanel(parent)
            # Only show the top most panel  
            if index == 0:
                panel.Show()
            else:
                panel.Hide()
            panel.SetSizer(view.view(panel))
            top_sizer.Add(panel, proportion=1, flag=wx.EXPAND)
        return top_sizer


class HomeNavPanel(ScrolledPanel):

    def __init__(self, parent):
        super().__init__(parent)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.SetupScrolling(scroll_x=False)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        dc.GradientFillLinear((0, 0, w, h), theme.GRID_BACKGROUND_START,
                              theme.GRID_BACKGROUND_STOP, nDirection=wx.BOTTOM)

