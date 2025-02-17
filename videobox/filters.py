'''
Custom Jinja Filters
'''
import operator
from collections import defaultdict
from pathlib import Path
import itertools
from urllib.parse import urlparse
from datetime import datetime, timezone
from videobox import iso639

MIN_SEEDERS = 1

def human_date(value):
    return value.strftime("%b %d, %Y")

def timeline_date(value):
    return value.strftime("%a, %b %d")

def to_date(value):
    return datetime.strptime(value, '%Y-%m-%d')

def human_date_time(value):
    return value.strftime("%b %d, %Y at %H:%M")

def datetime_since(since_value, current_value):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    # Make sure we are comparing two TZ-aware values
    diff = current_value.replace(tzinfo=timezone.utc) - since_value.replace(tzinfo=timezone.utc)

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

    return "just now"


def build_file_tree(file_paths):
    # Build a nested dictionary representing the file tree
    def file_tree(): 
        return defaultdict(file_tree)
    root = file_tree()

    for path in file_paths:
        parts = Path(path).parts
        current_level = root
        for part in parts:
            current_level = current_level[part]

    return root

def emit_file_tree_html(file_tree, indent=0):
    html = ""
    for key, value in file_tree.items():
        if value:  # It's a directory
            html += " " * indent + f'<li class="directory">{key}\n'
            html += " " * indent + "<ol>\n"
            html += emit_file_tree_html(value, indent + 2)
            html += " " * indent + "</ol>\n"
        else:  # It's a file
            html += " " * indent + f"<li>{key}\n"
        html += " " * indent + "</li>\n"
    return html

# def build_file_tree(file_paths):
#     file_tree = _build_file_tree(file_paths)
#     html = "<ol>\n"
#     html += _emit_html(file_tree)
#     html += "</ol>"
#     return html

# def timedelta(days):
#     periods = (
#         (days // 365, "year", "years"),
#         (days // 30, "month", "months"),
#         (days // 7, "week", "weeks"),
#         (days // 1, "day", "days"),
#     )

#     for period, singular, plural in periods:
#         if period:
#             return "in %d %s" % (period, singular if period == 1 else plural)

#     return "later today"

def islice(iterable, stop):
    return itertools.islice(iterable, stop)

def groupby_attrs(iterable, attr, *attrs):
    return itertools.groupby(iterable, key=operator.attrgetter(attr, *attrs))

def networks(value):
    pieces = value.split(", ")
    if len(pieces) > 1:
        return f"{pieces[0]} and others"
    else:
        return pieces[0]

def torrent_health(value):
    color = "hi"
    if MIN_SEEDERS <= value < 4:
        color = "low"
    elif 4 <= value < 7:
        color = "medium"
    return f'<span class="torrent-{color}">{value}</span>'

def lang(code):
    try:
        return iso639.LANGUAGES_SET_1[code]
    except KeyError:
        return 'Unknown'

def pluralize(number, singular='', plural='s'):
    if number == 1:
        return singular
    else:
        return plural

def nice_url(value): 
    pieces = urlparse(value)
    return pieces.netloc 

FILTERS = [
    human_date,
    timeline_date,
    human_date_time,
    torrent_health,
    networks,
    lang,
    islice,
    groupby_attrs,
    to_date,
    datetime_since,
    #timedelta,
    pluralize,
    nice_url,
]

def init_app(app):
    for func in FILTERS:
        app.add_template_filter(func)
