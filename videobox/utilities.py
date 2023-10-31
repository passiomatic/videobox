from datetime import datetime, date, timedelta

def plural(prefix, value):
    return f"{prefix}{'s' if value > 1 else ''}"


def sanitize_query(query):
    # https://www.sqlite.org/fts5.html
    sanitized_query = ""
    for c in query:
        if c.isalpha() or c.isdigit() or ord(c) > 127 or ord(c) == 96 or ord(c) == 26:
            # Allowed in FTS queries
            sanitized_query += c
        else:
            sanitized_query += " "
    return sanitized_query


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
