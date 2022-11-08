import wx 
import wx.lib.platebtn as platebtn

# Theme variables 

GRID_BACKGROUND_START = 'DARK GREY'
GRID_BACKGROUND_STOP = 'BLACK'

LABEL_COLOR = 'LIGHT GREY'
LABEL_COLOR_NORMAL = 'LIGHT GREY'
LABEL_COLOR_PRESSED = 'WHITE'

# View helpers 

def make_label(parent, text, color=None, scale=1.0):
    """
    Make a left-aligned text label, possibily larger or smaller than default font
    """
    label = wx.StaticText(
        parent, wx.ID_ANY, label=text, style=wx.ALIGN_LEFT)
    font = label.GetFont()
    font = font.MakeBold()
    font = font.Scale(scale)
    label.SetFont(font)
    if color:
        label.SetForegroundColour(color)
    return label

def make_button(parent, text):
    button = platebtn.PlateButton(parent, id=wx.ID_ANY, label=text, style=platebtn.PB_STYLE_SQUARE | platebtn.PB_STYLE_NOBG)
    button.SetLabelColor(normal=wx.Colour(LABEL_COLOR_NORMAL), hlight=wx.Colour(LABEL_COLOR_PRESSED))
    button.SetPressColor(wx.Colour(LABEL_COLOR_PRESSED))
    return button