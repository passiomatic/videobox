import wx 
from wx.lib.wordwrap import wordwrap
from wx.lib.stattext import GenStaticText

class AutoWrapStaticText(GenStaticText):
    """
    A simple class derived from :mod:`lib.stattext` that implements auto-wrapping
    behaviour depending on the parent size.
    """

    def __init__(self, parent, label):
        """
        Defsult class constructor.
        :param wx.Window parent: a subclass of :class:`wx.Window`, must not be ``None``;
        :param string `label`: the :class:`AutoWrapStaticText` text label.
        """

        super().__init__(parent, -1, label, style=wx.ST_NO_AUTORESIZE)

        self.label = label
        self.Bind(wx.EVT_SIZE, self.OnSize)


    def OnSize(self, event):
        """
        Handles the ``wx.EVT_SIZE`` event for :class:`AutoWrapStaticText`.
        :param `event`: a :class:`wx.SizeEvent` event to be processed.
        """

        event.Skip()
        self.Wrap(event.GetSize().width)


    def Wrap(self, width):
        """
        This functions wraps the controls label so that each of its lines becomes at
        most `width` pixels wide if possible (the lines are broken at words boundaries
        so it might not be the case if words are too long).
        If `width` is negative, no wrapping is done.
        :param integer `width`: the maximum available width for the text, in pixels.
        :note: Note that this `width` is not necessarily the total width of the control,
         since a few pixels for the border (depending on the controls border style) may be added.
        """

        if width < 0:
            return

        self.Freeze()

        dc = wx.ClientDC(self)
        dc.SetFont(self.GetFont())
        text = wordwrap(self.label, width, dc)
        self.SetLabel(text, wrapped=True)

        self.Thaw()


    def SetLabel(self, label, wrapped=False):
        """
        Sets the :class:`AutoWrapStaticText` label.
        All "&" characters in the label are special and indicate that the following character is
        a mnemonic for this control and can be used to activate it from the keyboard (typically
        by using ``Alt`` key in combination with it). To insert a literal ampersand character, you
        need to double it, i.e. use "&&". If this behaviour is undesirable, use :meth:`~Control.SetLabelText` instead.
        :param string `label`: the new :class:`AutoWrapStaticText` text label;
        :param bool `wrapped`: ``True`` if this method was called by the developer using :meth:`~AutoWrapStaticText.SetLabel`,
         ``False`` if it comes from the :meth:`~AutoWrapStaticText.OnSize` event handler.
        :note: Reimplemented from :class:`wx.Control`.
        """

        if not wrapped:
            self.label = label

        super().SetLabel(label)