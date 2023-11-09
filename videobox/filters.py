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

def to_date(value):
    return datetime.strptime(value, '%Y-%m-%d')

def human_date_time(value):
    return value.strftime("%b %d, %Y at %H:%M")

def islice(iterable, stop):
    return itertools.islice(iterable, stop)

def groupby_attrs(iterable, attr, *attrs):
    return itertools.groupby(iterable, key=operator.attrgetter(attr, *attrs))

def networks(value):
    pieces = value.split(", ")
    # Show up to 3 networks
    if len(pieces) < 4:
        return " • ".join(pieces)
    else:
        return f"{pieces[0]} and others"

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

FILTERS = [
    human_date,
    human_date_time,
    torrent_health,
    networks,
    lang,
    islice,
    groupby_attrs,
    to_date
]

def init_app(app):
    for func in FILTERS:
        app.add_template_filter(func)
