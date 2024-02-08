from datetime import datetime, date
from operator import attrgetter
from itertools import groupby
import queue
import flask
from flask import current_app as app
from peewee import fn, JOIN
from playhouse.flask_utils import PaginatedQuery, get_object_or_404
import videobox
import videobox.models as models
from videobox.models import Series, Episode, Release, Tag, SeriesTag, SyncLog
import videobox.sync as sync
from . import bp
from . import queries

MAX_TOP_TAGS = 10
MAX_SEASONS = 2
MIN_SEEDERS = 1
MAX_LOG_ROWS = 20
SERIES_CARDS_PER_PAGE = 6 * 10
SERIES_EPISODES_PER_PAGE = 30
RESOLUTION_OPTIONS = {
    0: "Any",
    480: "480p",
    720: "720p (HD)",
    1080: "1080p (Full HD)",
    2160: "2160p (4K)",
}
SIZE_OPTIONS = {
    "": "Any",
    "asc": "Smallest",
    "desc": "Largest",
}


@bp.context_processor
def inject_template_vars():
    return {
        "last_sync": models.get_last_log(),
        "version": videobox.__version__
    }


@bp.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


# ---------
# Home
# ---------

last_server_alert = ''

@bp.route('/')
def home():
    total_series, total_episodes, total_releases = queries.get_library_stats()
    if total_series:        
        utc_now = datetime.utcnow()
        today_series = queries.get_today_series()
        # Do not exlude any series for now
        exclude_ids = []
        featured_series = queries.get_featured_series(exclude_ids=exclude_ids, days_interval=2).limit(8)
        top_tags = queries.get_nav_tags(8)    
        # Show updates within the last week
        followed_series = queries.get_followed_series(days=7)
        return flask.render_template("home.html", 
                                     utc_now=utc_now,
                                     server_alert=last_server_alert,
                                     today_series=today_series,
                                     featured_series=featured_series, 
                                     top_tags=top_tags,
                                     total_series=total_series,
                                     #total_episodes=total_episodes,
                                     total_releases=total_releases,
                                     followed_series=followed_series)
    else:
        return flask.render_template("first-import.html")

# ---------
# Search
# ---------


@bp.route('/search')
def search():
    query = flask.request.args.get("query")
    series_ids = [series.rowid for series in queries.search_series(
        sanitize_query(query))]
    series = queries.get_series_with_ids(series_ids)
    # @@TODO
    # if len(series) == 1:
    #     # Single match, display series detail page
    return flask.render_template("search_results.html", found_series=series, search_query=query)


@bp.route('/suggest')
def suggest():
    query = flask.request.args.get("query")
    sanitized_query = sanitize_query(query)
    search_suggestions = queries.suggest_series(sanitized_query).limit(10)
    return flask.render_template("_suggest.html", search_suggestions=search_suggestions)


# ---------
# Tag
# ---------

@bp.route('/tag')
def tag():    
    tags_all = queries.get_top_series_for_tags()
    tags_series = groupby(tags_all, key=attrgetter('tag_slug', 'tag_name'))
    return flask.render_template("tags.html", tags_series=tags_series)


@bp.route('/tag/<slug>')
def tag_detail(slug):
    page = flask.request.args.get("page", 1, type=int)
    tag = get_object_or_404(Tag, (Tag.slug == slug))
    query = queries.get_series_for_tag(tag)
    paginated_series = PaginatedQuery(query, paginate_by=SERIES_CARDS_PER_PAGE, page_var="page", check_bounds=True)
    if page == 1:
        return flask.render_template("tag_detail.html", tag=tag, series=paginated_series, page=page, series_count=query.count())
    else:
        # For async requests
        return flask.render_template("_tag-card-grid.html", tag=tag, series=paginated_series, page=page)

# ---------
# Languages
# ---------

@bp.route('/language/<code>')
def language_detail(code):
    page = flask.request.args.get("page", 1, type=int)
    query = queries.get_series_for_language(code)
    paginated_series = PaginatedQuery(query, paginate_by=SERIES_CARDS_PER_PAGE, page_var="page", check_bounds=True)
    if page == 1:
        return flask.render_template("language_detail.html", language=code, series=paginated_series, page=page, series_count=query.count())
    else:
        # For async requests
        return flask.render_template("_language-card-grid.html", language=code, series=paginated_series, page=page)


# --------- 
# Series Detail
# ---------


@bp.route('/series/<int:series_id>')
def series_detail(series_id):
    #resolution = flask.request.args.get("resolution", type=int, default=0) or flask.request.cookies.get('resolution', type=int, default=0)
    resolution = flask.request.args.get("resolution", type=int, default=0)
    #size_sorting = flask.request.args.get("size", default="") or flask.request.cookies.get('size', default="")
    size_sorting = flask.request.args.get("size", default="")
    view_layout = flask.request.args.get("view", default="grid")
    today = date.today()
    series = get_object_or_404(Series, (Series.id == series_id))
    series_subquery = queries.get_series_subquery()
    release_cte = queries.release_cte(resolution, size_sorting)
    if resolution or size_sorting:
        episodes_query = (Episode.select(Episode, Release.id, Release.name, Release.magnet_uri, Release.resolution, Release.size, Release.seeders, Release.last_updated_on)
                          .join(Release)
                          .switch(Episode)
                          .join(Series)
                          .join(series_subquery, on=(
                              series_subquery.c.id == Series.id))
                          .join(release_cte, on=(Release.id == release_cte.c.release_id))
                          .where((Episode.series == series.id) &
                                 # Episodes from last 2 seasons only
                                 (series_subquery.c.max_season - Episode.season < MAX_SEASONS) &
                                 (Episode.aired_on != None)
                                 )
                          .order_by(Episode.season.desc(), Episode.number)
                          .with_cte(release_cte))
    else:
        # Unfiltered
        episodes_query = (Episode.select(Episode, Release.id, Release.name, Release.magnet_uri, Release.resolution, Release.size, Release.seeders, Release.last_updated_on)
                          .join(Release, JOIN.LEFT_OUTER)
                          .switch(Episode)
                          .join(Series)
                          .join(series_subquery, on=(
                              series_subquery.c.id == Series.id))
                          .where((Episode.series == series.id) &
                                 # Episodes from last 2 seasons only
                                 (series_subquery.c.max_season - Episode.season < MAX_SEASONS) &
                                 (Episode.aired_on != None)
                                 )
                          .order_by(Episode.season.desc(), Episode.number, Release.seeders.desc()))

    # Group by season number
    seasons_episodes = groupby(episodes_query, key=attrgetter('season'))
    series_tags = queries.get_series_tags(series) 

    response = flask.make_response(flask.render_template("series_detail.html", 
                                                         series=series, 
                                                         series_tags=series_tags, 
                                                         seasons_episodes=seasons_episodes, 
                                                         today=today, 
                                                         resolution=resolution, 
                                                         resolution_options=RESOLUTION_OPTIONS, 
                                                         size=size_sorting, 
                                                         size_options=SIZE_OPTIONS,
                                                         view_layout=view_layout))
    # Remember filters across requests
    if resolution:
        response.set_cookie('resolution', str(resolution))
    if size_sorting:
        response.set_cookie('size', size_sorting)    
    return response


@bp.route('/series/follow/<int:series_id>', methods=['POST'])
def series_detail_update(series_id):
    following = flask.request.form.get("following", type=int)
    series = get_object_or_404(Series, (Series.id == series_id))
    series.followed_since = date.today() if following else None
    series.save()

    # Toggle button
    return flask.render_template("_follow-button.html", series=series)

@bp.route('/release/<int:release_id>')
def release_detail(release_id):
    utc_now = datetime.utcnow()
    release = get_object_or_404(Release, (Release.id == release_id))
    return flask.render_template("_release_detail.html", utc_now=utc_now, release=release)


@bp.route('/following')
def following():
    page = flask.request.args.get("page", 1, type=int)
    query = queries.get_followed_series()
    paginated_series = PaginatedQuery(query, paginate_by=SERIES_EPISODES_PER_PAGE, page_var="page")
    if page == 1:
        return flask.render_template("following.html", paginated_series=paginated_series, page=page)
    else:
        # For async requests
        return flask.render_template("_following.html", paginated_series=paginated_series, page=page)
        

    
# ---------
# Update database
# ---------

close_message = object()

class MessageAnnouncer(object):
    """
    Server-sent events in Flask without extra dependencies.
    See https://maxhalford.github.io/blog/flask-sse-no-deps/
    """

    def __init__(self):
        self.listeners = []

    def listen(self):
        q = queue.Queue(maxsize=5)
        self.listeners.append(q)
        return q

    def format_sse(self, data, event=None):
        msg = f'data: {data}\n\n'
        if event:
            msg = f'event: {event}\n{msg}'
        return msg

    def announce(self, msg):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]


announcer = MessageAnnouncer()
sync_worker = None

@bp.route('/update')
def update():

    @flask.copy_current_request_context
    def on_update_progress(message, percent=0):
        data = flask.render_template(
            "_update-dialog.html", message=message, percent=percent)
        msg = announcer.format_sse(data=data, event='updating')
        announcer.announce(msg)

    @flask.copy_current_request_context
    def on_update_done(message, alert):
        data = flask.render_template(
            "_update-dialog-done.html", message=message, percent=100)
        msg = announcer.format_sse(data=data, event='done')
        announcer.announce(msg)
        announcer.announce(close_message)
        global last_server_alert
        last_server_alert = alert

    global sync_worker 
    if sync_worker and sync_worker.is_alive():
        app.logger.warning("Sync is already running, request ignored")
    else:
        sync_worker = sync.SyncWorker(
            app.config["API_CLIENT_ID"], progress_callback=on_update_progress, done_callback=on_update_done)
        sync_worker.start()

    return {}, 200

@bp.route('/update-events')
def update_events():    
    def stream():
        # Returns a queue.Queue
        messages = announcer.listen()
        while True:
            # Blocks until a new message arrives
            msg = messages.get()
            if msg is close_message:
                break
            yield msg
    return flask.Response(stream(), mimetype='text/event-stream')


@bp.route('/update/history')
def update_history():
    log_rows = SyncLog.select().order_by(SyncLog.timestamp.desc()).limit(MAX_LOG_ROWS)
    return flask.render_template("log.html", log_rows=log_rows, max_log_rows=MAX_LOG_ROWS)

# ---------
# Helpers
# ---------

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