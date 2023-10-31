from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from operator import attrgetter
from itertools import groupby, islice
import queue
import flask
from flask import current_app as app
from flask import Flask
from peewee import fn, JOIN
from playhouse.flask_utils import PaginatedQuery, get_object_or_404
import videobox
import videobox.models as models
from videobox.models import Series, Episode, Release, Tag, SeriesTag
import videobox.utilities as utilities
import videobox.sync as sync
from . import bp
from . import queries

MAX_TOP_TAGS = 10
MAX_SEASONS = 2
MIN_SEEDERS = 1
SERIES_PER_PAGE = 6 * 10
APP_DIR = Path.home().joinpath(".videobox")
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
        today_series = queries.get_today_series()
        today_series_tags = None
        exclude_ids = []
        if today_series:
            today_series_tags = queries.get_series_tags(today_series) 
            exclude_ids = [today_series.id]
        featured_series = queries.get_featured_series(exclude_ids=exclude_ids, days_interval=2).limit(8)
        top_tags = queries.get_nav_tags(8)
        return flask.render_template("home.html", 
                                    server_alert=last_server_alert,
                                    today_series=today_series,
                                    today_series_tags=today_series_tags,
                                    featured_series=featured_series, 
                                    top_tags=top_tags,
                                    total_series=total_series,
                                    total_episodes=total_episodes,
                                    total_releases=total_releases)
    else:
        return flask.render_template("first-import.html")

# ---------
# Search
# ---------


@bp.route('/search')
def search():
    query = flask.request.args.get("query")
    series_ids = [series.rowid for series in queries.search_series(
        utilities.sanitize_query(query))]
    series = queries.get_series_with_ids(series_ids)
    # @@TODO
    # if len(results) == 1:
    #     # Single match, display series detail page
    #     series = models.get_series(results[0].rowid)
    return flask.render_template("search_results.html", found_series=series, search_query=query)


@bp.route('/suggest')
def suggest():
    query = flask.request.args.get("query")
    sanitized_query = utilities.sanitize_query(query)
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
    paginated_series = PaginatedQuery(query, paginate_by=SERIES_PER_PAGE, page_var="page", check_bounds=True)
    if page == 1:
        return flask.render_template("tag_detail.html", tag=tag, series=paginated_series, page=1, series_count=query.count())
    else:
        # For async requests
        return flask.render_template("_tag-card-grid.html", tag=tag, series=paginated_series, page=page)

# --------- 
# Series Detail
# ---------


@bp.route('/series/<int:series_id>')
def series_detail(series_id):
    #resolution = flask.request.args.get("resolution", type=int, default=0) or flask.request.cookies.get('resolution', type=int, default=0)
    resolution = flask.request.args.get("resolution", type=int, default=0)
    #size_sorting = flask.request.args.get("size", default="") or flask.request.cookies.get('size', default="")
    size_sorting = flask.request.args.get("size", default="")
    today = date.today()
    series = get_object_or_404(Series, (Series.id == series_id))
    series_subquery = queries.get_series_subquery()
    release_cte = queries.release_cte(resolution, size_sorting)
    if resolution or size_sorting:
        episodes_query = (Episode.select(Episode.id, Episode.name, Episode.season, Episode.number, Episode.aired_on, Release.id, Release.name, Release.magnet_uri, Release.resolution, Release.size, Release.seeders, Release.last_updated_on)
                        .join(Release)
                        .switch(Episode)
                        .join(Series)
                        .join(series_subquery, on=(
                            series_subquery.c.id == Series.id))
                        .join(release_cte, on=(Release.id == release_cte.c.release_id))
                        .where((Episode.series == series.id)
                                # Episodes from last 2 seasons only
                                & (series_subquery.c.max_season - Episode.season < MAX_SEASONS)
                                & (Episode.aired_on != None)
                                )
                        .order_by(Episode.season.desc(), Episode.number)
                        .with_cte(release_cte))
    else:
        # Unfiltered
        episodes_query = (Episode.select(Episode.id, Episode.name, Episode.season, Episode.number, Episode.aired_on, Release.id, Release.name, Release.magnet_uri, Release.resolution, Release.size, Release.seeders, Release.last_updated_on)
                        .join(Release, JOIN.LEFT_OUTER)
                        .switch(Episode)
                        .join(Series)
                        .join(series_subquery, on=(
                            series_subquery.c.id == Series.id))
                        .where((Episode.series == series.id)
                                # Episodes from last 2 seasons only
                                & (series_subquery.c.max_season - Episode.season < MAX_SEASONS)
                                & (Episode.aired_on != None)
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
        size_options=SIZE_OPTIONS))
    # Remember filters across requests
    if resolution:
        response.set_cookie('resolution', str(resolution))
    if size_sorting:
        response.set_cookie('size', size_sorting)    
    return response


@bp.route('/release/<int:release_id>')
def release_detail(release_id):
    release = get_object_or_404(Release, (Release.id == release_id))
    return flask.render_template("_release_detail.html", release=release)


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
