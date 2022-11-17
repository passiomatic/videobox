
__all__ = ["LabelButton",
           "PLATE_NORMAL", "PLATE_PRESSED", "PLATE_HIGHLIGHT",

           "LB_STYLE_TOGGLE"]

#-----------------------------------------------------------------------------#
# Imports
import wx
import wx.lib.newevent

# Local Imports
from wx.lib.colourutils import *

#-----------------------------------------------------------------------------#
# Button States
PLATE_NORMAL = 0
PLATE_PRESSED = 1
PLATE_HIGHLIGHT = 2

# Button Styles
LB_STYLE_TOGGLE = 32  # Stay pressed until clicked again

#-----------------------------------------------------------------------------#

# EVT_BUTTON used for normal event notification
# EVT_TOGGLE_BUTTON used for toggle button mode notification

#-----------------------------------------------------------------------------#

class LabelButton(wx.Control):
    """LabelButton is a custom type of flat button with support for
    displaying bitmaps and having an attached dropdown menu.

    """
    def __init__(self, parent, id=wx.ID_ANY, label='',
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0, name=wx.ButtonNameStr):
        """Create a LabelButton

        :keyword string `label`: Buttons label text
        :keyword wx.Bitmap `bmp`: Buttons bitmap
        :keyword `style`: Button style

        """
        super().__init__(parent, id, pos, size,
                wx.BORDER_NONE|wx.TRANSPARENT_WINDOW,
                name=name)

        # Attributes
        self.InheritAttributes()
        self.SetLabel(label)
        self._style = style
        self._state = dict(pre=PLATE_NORMAL, cur=PLATE_NORMAL)
        self._color = self.__InitColors()
        self._pressed = False

        # Setup Initial Size
        self.SetInitialSize(size)

        # Event Handlers
        self.Bind(wx.EVT_PAINT, lambda evt: self.__DrawButton())
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

        # Mouse Events
        self.Bind(wx.EVT_LEFT_DCLICK, lambda evt: self._ToggleState())
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_ENTER_WINDOW,
                  lambda evt: self._SetState(PLATE_HIGHLIGHT))
        self.Bind(wx.EVT_LEAVE_WINDOW,
                  lambda evt: wx.CallLater(80, self.__LeaveWindow))

        # Other events
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)


    def __DrawHighlight(self, gc, width, height):
        """Draw the main highlight/pressed state

        :param wx.GCDC `gc`: :class:`wx.GCDC` to draw with
        :param int `width`: width of highlight
        :param int `height`: height of highlight

        """
        if self._state['cur'] == PLATE_PRESSED:
            color = self._color['press']
        else:
            color = self._color['hlight']

        gc.SetBrush(wx.Brush(color))


    def __PostEvent(self):
        """Post a button event to parent of this control"""
        if self._style & LB_STYLE_TOGGLE:
            etype = wx.wxEVT_COMMAND_TOGGLEBUTTON_CLICKED
        else:
            etype = wx.wxEVT_COMMAND_BUTTON_CLICKED
        bevt = wx.CommandEvent(etype, self.GetId())
        bevt.SetEventObject(self)
        bevt.SetString(self.GetLabel())
        self.GetEventHandler().ProcessEvent(bevt)


    def __DrawButton(self):
        """Draw the button"""
        dc = wx.PaintDC(self)
        gc = wx.GCDC(dc)

        # Setup
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.SetFont(self.Font)
        dc.SetFont(self.Font)
        gc.SetBackgroundMode(wx.TRANSPARENT)

        # The background needs some help to look transparent on
        # on Gtk and Windows
        if wx.Platform in ['__WXGTK__', '__WXMSW__']:
            gc.SetBackground(self.GetBackgroundBrush(gc))
            gc.Clear()

        # Calc Object Positions
        width, height = self.GetSize()
        if wx.Platform == '__WXGTK__':
            tw, th = dc.GetTextExtent(self.Label)
        else:
            tw, th = gc.GetTextExtent(self.Label)
        txt_y = max((height - th) // 2, 1)

        if self._state['cur'] == PLATE_HIGHLIGHT:
            gc.SetTextForeground(self._color['htxt'])
            gc.SetPen(wx.TRANSPARENT_PEN)
            self.__DrawHighlight(gc, width, height)

        elif self._state['cur'] == PLATE_PRESSED:
            gc.SetTextForeground(self._color['htxt'])
            if wx.Platform == '__WXMAC__':
                pen = wx.Pen(GetHighlightColour(), 1, wx.PENSTYLE_SOLID)
            else:
                pen = wx.Pen(AdjustColour(self._color['press'], -80, 220), 1)
            gc.SetPen(pen)

            self.__DrawHighlight(gc, width, height)
            txt_x = 0
            if wx.Platform == '__WXGTK__':
                dc.DrawText(self.Label, txt_x, txt_y)
            else:
                gc.DrawText(self.Label, txt_x, txt_y)

        else:
            if self.IsEnabled():
                gc.SetTextForeground(self.GetForegroundColour())
            else:
                txt_c = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
                gc.SetTextForeground(txt_c)

        # Draw text
        if self._state['cur'] != PLATE_PRESSED:
            txt_x = 0
            if wx.Platform == '__WXGTK__':
                dc.DrawText(self.Label, txt_x, txt_y)
            else:
                gc.DrawText(self.Label, txt_x, txt_y)

    def __InitColors(self):
        """Initialize the default colors"""
        color = GetHighlightColour()
        pcolor = AdjustColour(color, -12)
        colors = dict(default=True,
                      hlight=color,
                      press=pcolor,
                      htxt=BestLabelColour(self.GetForegroundColour()))
        return colors


    def __LeaveWindow(self):
        """Handle updating the buttons state when the mouse cursor leaves"""
        if (self._style & LB_STYLE_TOGGLE) and self._pressed:
            self._SetState(PLATE_PRESSED)
        else:
            self._SetState(PLATE_NORMAL)
            self._pressed = False


    def _SetState(self, state):
        """Manually set the state of the button

        :param `state`: one of the PLATE_* values

        .. note::
            the state may be altered by mouse actions

        .. note::
            Internal use only!

        """
        self._state['pre'] = self._state['cur']
        self._state['cur'] = state
        if wx.Platform == '__WXMSW__':
            self.Parent.RefreshRect(self.Rect, False)
        else:
            self.Refresh()


    def _ToggleState(self):
        """Toggle button state

        ..note::
            Internal Use Only!

        """
        if self._state['cur'] != PLATE_PRESSED:
            self._SetState(PLATE_PRESSED)
        else:
            self._SetState(PLATE_HIGHLIGHT)

    #---- Public Member Functions ----#

    LabelText = property(lambda self: self.GetLabel(),
                         lambda self, lbl: self.SetLabel(lbl))


    def AcceptsFocus(self):
        """Can this window have the focus?"""
        return self.IsEnabled()


    def Disable(self):
        """Disable the control"""
        super().Disable()
        self.Refresh()


    def DoGetBestSize(self):
        """Calculate the best size of the button

        :return: :class:`wx.Size`

        """
        width = 4
        height = 6
        if self.Label:
            # NOTE: Should measure with a GraphicsContext to get right
            #       size, but due to random segfaults on linux special
            #       handling is done in the drawing instead...
            lsize = self.GetFullTextExtent(self.Label)
            width += lsize[0]
            height += lsize[1]

        width += 10

        best = wx.Size(width, height)
        self.CacheBestSize(best)
        return best


    def Enable(self, enable=True):
        """Enable/Disable the control"""
        super().Enable(enable)
        self.Refresh()


    def GetBackgroundBrush(self, dc):
        return wx.TRANSPARENT_BRUSH


    # Alias for GetLabel
    GetLabelText = wx.Control.GetLabel


    def GetState(self):
        """Get the current state of the button

        :return: int

        .. seeAlso::
            PLATE_NORMAL, PLATE_HIGHLIGHT, PLATE_PRESSED

        """
        return self._state['cur']


    def HasTransparentBackground(self):
        """Override setting of background fill"""
        return True


    def IsPressed(self):
        """Return if button is pressed (LB_STYLE_TOGGLE)

        :return: bool

        """
        return self._pressed


    #---- Event Handlers ----#

    def OnErase(self, evt):
        """Trap the erase event to keep the background transparent
        on windows.

        :param `evt`: wx.EVT_ERASE_BACKGROUND

        """
        pass


    def OnFocus(self, evt):
        """Set the visual focus state if need be"""
        if self._state['cur'] == PLATE_NORMAL:
            self._SetState(PLATE_HIGHLIGHT)


    def OnKeyUp(self, evt):
        """Execute a single button press action when the Return key is pressed
        and this control has the focus.

        :param `evt`: wx.EVT_KEY_UP

        """
        if evt.GetKeyCode() == wx.WXK_SPACE:
            self._SetState(PLATE_PRESSED)
            self.__PostEvent()
            wx.CallLater(100, self._SetState, PLATE_HIGHLIGHT)
        else:
            evt.Skip()


    def OnKillFocus(self, evt):
        """Set the visual state back to normal when focus is lost
        unless the control is currently in a pressed state.

        """
        # Note: this delay needs to be at least as much as the on in the KeyUp
        #       handler to prevent ghost highlighting from happening when
        #       quickly changing focus and activating buttons
        if self._state['cur'] != PLATE_PRESSED:
            self._SetState(PLATE_NORMAL)


    def OnLeftDown(self, evt):
        """Sets the pressed state and depending on the click position will
        show the popup menu if one has been set.

        """
        if (self._style & LB_STYLE_TOGGLE):
            self._pressed = not self._pressed

        self._SetState(PLATE_PRESSED)
        self.SetFocus()


    def OnLeftUp(self, evt):
        """Post a button event if the control was previously in a
        pressed state.

        :param `evt`: :class:`wx.MouseEvent`

        """
        self.__PostEvent()
        if self._pressed:
            self._SetState(PLATE_PRESSED)
        else:
            self._SetState(PLATE_HIGHLIGHT)


    def OnMenuClose(self, evt):
        """Refresh the control to a proper state after the menu has been
        dismissed.

        :param `evt`: wx.EVT_MENU_CLOSE

        """
        mpos = wx.GetMousePosition()
        if self.HitTest(self.ScreenToClient(mpos)) != wx.HT_WINDOW_OUTSIDE:
            self._SetState(PLATE_HIGHLIGHT)
        else:
            self._SetState(PLATE_NORMAL)
        evt.Skip()

    #---- End Event Handlers ----#

    def SetFocus(self):
        """Set this control to have the focus"""
        if self._state['cur'] != PLATE_PRESSED:
            self._SetState(PLATE_HIGHLIGHT)
        super().SetFocus()


    def SetFont(self, font):
        """Adjust size of control when font changes"""
        super().SetFont(font)
        self.InvalidateBestSize()


    def SetLabel(self, label):
        """Set the label of the button

        :param string `label`: label string

        """
        super().SetLabel(label)
        self.InvalidateBestSize()


    def SetLabelColor(self, normal, hlight=wx.NullColour):
        """Set the color of the label. The optimal label color is usually
        automatically selected depending on the button color. In some
        cases the colors that are chosen may not be optimal.

        The normal state must be specified, if the other two params are left
        Null they will be automatically guessed based on the normal color. To
        prevent this automatic color choices from happening either specify
        a color or None for the other params.

        :param wx.Colour `normal`: Label color for normal state (:class:`wx.Colour`)
        :keyword wx.Colour `hlight`: Color for when mouse is hovering over

        """
        assert isinstance(normal, wx.Colour), "Must supply a colour object"
        self._color['default'] = False
        self.SetForegroundColour(normal)

        if hlight is not None:
            if hlight.IsOk():
                self._color['htxt'] = hlight
            else:
                self._color['htxt'] = BestLabelColour(normal)

        if wx.Platform == '__WXMSW__':
            self.Parent.RefreshRect(self.GetRect(), False)
        else:
            self.Refresh()


    def SetPressColor(self, color):
        """Set the color used for highlighting the pressed state

        :param wx.Colour `color`: :class:`wx.Colour`

        .. note::
            also resets all text colours as necessary

        """
        self._color['default'] = False
        if color.Alpha() == 255:
            self._color['hlight'] = AdjustAlpha(color, 200)
        else:
            self._color['hlight'] = color
        self._color['press'] = AdjustColour(color, -10, 160)
        self._color['htxt'] = BestLabelColour(self._color['hlight'])
        self.Refresh()


    def SetWindowStyle(self, style):
        """Sets the window style bytes, the updates take place
        immediately no need to call refresh afterwards.

        :param `style`: bitmask of PB_STYLE_* values

        """
        self._style = style
        self.Refresh()


    def SetWindowVariant(self, variant):
        """Set the variant/font size of this control"""
        super().SetWindowVariant(variant)
        self.InvalidateBestSize()


    def ShouldInheritColours(self):
        """Overridden base class virtual. If the parent has non-default
        colours then we want this control to inherit them.

        """
        return True
