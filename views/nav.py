
import wx
import logging
import views.theme as theme
from pubsub import pub
from wx.lib.scrolledpanel import ScrolledPanel

MSG_BACK_CLICKED = "back.clicked"

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
        if self.is_home():
            logging.warn("Cannot go back when in home, command ignored")
        else:
            view = self.views.pop()
            #panel.HideWithEffect(wx.SHOW_EFFECT_SLIDE_TO_RIGHT, timeout=300)

    def is_home(self):
        return len(self.views) == 1

    def render(self, parent) -> wx.BoxSizer:
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        back_button = wx.Button(parent, label="Back")
        back_button.Bind(wx.EVT_BUTTON, lambda event: pub.sendMessage(MSG_BACK_CLICKED))
        # if self.is_home():
        #     back_button.Hide()
        top_sizer.Add(back_button, proportion=0, flag=wx.ALL, border=5)
        for index, view in enumerate(reversed(self.views)):
            panel = HomeNavPanel(parent)
            # Only show the top most panel  
            if index == 0:
                panel.Show()
            else:
                panel.Hide()
            panel.SetSizer(view.render(panel))
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

