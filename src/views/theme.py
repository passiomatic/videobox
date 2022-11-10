import wx 
import wx.lib.platebtn as platebtn
from datetime import date

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

def make_pill(parent, text):
    #@@TODO Round corners
    pill = wx.StaticText(parent, label=text)
    font = pill.GetFont()
    #font = font.Scale(scale)
    #pill.SetFont(font)
    pill.SetForegroundColour(LABEL_COLOR_NORMAL)
    pill.SetBackgroundColour(GRID_BACKGROUND_START)
    
    return pill    

def make_button(parent, text):
    button = platebtn.PlateButton(parent, id=wx.ID_ANY, label=text, style=platebtn.PB_STYLE_SQUARE | platebtn.PB_STYLE_NOBG)
    button.SetLabelColor(normal=wx.Colour(LABEL_COLOR_NORMAL), hlight=wx.Colour(LABEL_COLOR_PRESSED))
    button.SetPressColor(wx.Colour(LABEL_COLOR_PRESSED))
    return button


def format_size(value):
    prefix = ['B', 'kB', 'MB', 'GB', 'TB']
    for i in range(len(prefix)):
        if abs(value) < 1000:
            if i == 0:
                return '%5.3g%s' % (value, prefix[i])
            else:
                return '%4.3g%s' % (value, prefix[i])
        value /= 1000

    return '%6.3gPB' % value


def format_date(value):
    # Use NY Times format 
    return value.strftime("%b. %d, %Y")

def datetime_since(value, comparison_value, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    diff = comparison_value - value
    
    periods = (
        (diff.days // 365, "year", "years"),
        (diff.days // 30, "month", "months"),
        (diff.days // 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds // 3600, "hour", "hours"),
        (diff.seconds // 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:        
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default
