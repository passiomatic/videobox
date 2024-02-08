'''
Custom Jinja Filters
'''
import operator
import itertools
from datetime import datetime
from videobox import languages

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

    diff = current_value - since_value

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
        return languages.LANGUAGES[code]
    except KeyError:
        return ''

def pluralize(prefix, value):
    return f"{prefix}{'s' if value > 1 else ''}"

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
    pluralize
]

def init_app(app):
    for func in FILTERS:
        app.add_template_filter(func)
