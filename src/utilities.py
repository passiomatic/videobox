from datetime import datetime, date, timedelta
from configuration import TAGS

def get_series_genre(series):
    return map(lambda slug: TAGS[slug], filter(lambda tag: tag in TAGS, series['tags']))

# def label_red(value):
#     return u"[COLOR tomato]{0}[/COLOR]".format(value) 

# def label_green(value):
#     return u"[COLOR green]{0}[/COLOR]".format(value) 

# def label_yellow(value):
#     return u"[COLOR yellow]{0}[/COLOR]".format(value) 

# def label_blue(value):
#     return u"[COLOR blue]{0}[/COLOR]".format(value) 

def scale_between(value, minAllowed, maxAllowed, min, max):
    return (maxAllowed - minAllowed) * (value - min) / (max - min) + minAllowed