import wx 

# Theme variables 

GRID_BACKGROUND_START = 'DARK GREY'
GRID_BACKGROUND_STOP = 'BLACK'

LABEL_COLOR = 'LIGHT GREY'

# View helpers 

def make_label(parent, text, scale=1.0):
    """
    Make a left-aligned text label, possibily larger or smaller than default font
    """
    label = wx.StaticText(
        parent, wx.ID_ANY, label=text, style=wx.ALIGN_LEFT)
    font = label.GetFont()
    font = font.MakeBold()
    font = font.Scale(scale)
    label.SetFont(font)
    label.SetForegroundColour(LABEL_COLOR)
    return label