# coding: utf-8

from datetime import datetime, date, timedelta
import time
import sqlite3
from configuration import TAGS

# Really weird issue, see https://forum.kodi.tv/showthread.php?tid=112916
def parse_datetime(value, format):
    try:
        return datetime.strptime(value, format)
    except TypeError:
        # Use time.strptime instead
        return datetime(*(time.strptime(value, format)[0:6]))    

def get_series_genre(series):
    return map(lambda slug: TAGS[slug], filter(lambda tag: tag in TAGS, series['tags']))

def label_red(value):
    return u"[COLOR tomato]{0}[/COLOR]".format(value) 

def label_green(value):
    return u"[COLOR green]{0}[/COLOR]".format(value) 

def label_yellow(value):
    return u"[COLOR yellow]{0}[/COLOR]".format(value) 

def label_blue(value):
    return u"[COLOR blue]{0}[/COLOR]".format(value) 

def to_datetime(value):
    return parse_datetime(value, '%Y-%m-%dT%H:%M:%S+00:00')

def to_date(value):
    return parse_datetime(value, '%Y-%m-%d').date()
    
def datetime_since(value, comparison_value, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    diff = comparison_value - value
    
    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:        
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default

def size_of(value, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(value) < 1024.0:
            return "%3.1f%s%s" % (value, unit, suffix)
        value /= 1024.0
    return "%.1f%s%s" % (value, 'Yi', suffix)

def scale_between(value, minAllowed, maxAllowed, min, max):
    return (maxAllowed - minAllowed) * (value - min) / (max - min) + minAllowed

# -----------
# Sqlite features
# -----------

def if_sqlite_version_and_up(version):
    return sqlite3.sqlite_version_info >= version