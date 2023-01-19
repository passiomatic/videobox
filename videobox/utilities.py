from datetime import datetime, date, timedelta


def format_size(value):
    prefix = ['B', 'kB', 'MB', 'GB', 'TB']
    for i in range(len(prefix)):
        if abs(value) < 1000:
            return '%.2f%s' % (value, prefix[i])
        value /= 1000

    return '%.fPB' % value


def format_date(value):
    return value.strftime("%b. %d, %Y")


def format_datetime(value):
    return value.strftime("%b. %d, %Y %H:%M")


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