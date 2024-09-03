from datetime import datetime, date, timezone
from operator import attrgetter
from itertools import groupby
import re
import flask
from flask import current_app as app
from peewee import fn, JOIN
from playhouse.flask_utils import PaginatedQuery, get_object_or_404
import videobox
import videobox.bt as bt
import videobox.models as models
from videobox.models import Series, Episode, Release, Tag, SeriesTag, SyncLog, Tracker, Torrent
from . import bp
from .announcer import announcer
from . import queries

MAX_CHART_DAYS = 30 
MAX_TOP_TAGS = 8
MIN_SEEDERS = 1
MAX_SEASONS = 2
MAX_LOG_ROWS = 3
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
RE_INFO_HASH = re.compile(r"^[0-9a-fA-F]{40}$")


@bp.context_processor
def inject_template_vars():
    return {
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
    # Make sure library is already filled with data
    if total_series and total_episodes and total_releases:        
        last_sync = models.get_last_log()
        utc_now = datetime.now(timezone.utc)
        today_series = queries.get_today_series(10)
        # Do not exclude any series for now
        exclude_ids = []
        featured_series = queries.get_featured_series(exclude_ids=exclude_ids, days_interval=2).limit(8)
        top_tags = queries.get_top_tags(MAX_TOP_TAGS)
        # Show updates within the last week
        followed_series = queries.get_followed_series(days=7)
        return flask.render_template("home.html", 
                                     last_sync=last_sync,
                                     utc_now=utc_now,
                                     server_alert=last_server_alert,
                                     today_series=today_series,
                                     featured_series=featured_series, 
                                     top_tags=top_tags,
                                     total_series=total_series,
                                     total_releases=total_releases,
                                     followed_series=followed_series)
    else:
        return flask.render_template("first-import.html")


@bp.route('/download/<int:release_id>', methods=['POST'])
def download_torrent(release_id):
    template = flask.request.form.get('template', '_download-button')
    release = Release.get_or_none(Release.id == release_id)
    if bt.torrent_worker and release:    
        bt.torrent_worker.add_torrents([release])
    else:
        flask.abort(404)

    return flask.render_template(f'{template}.html', release=release, status=models.TORRENT_ADDED)

@bp.route('/download-progress')
def download_progress():
    response = []
    if bt.torrent_worker:
        for t in bt.torrent_worker.transfers:
            response.append({
                'info_hash': t.info_hash,
                'progress': t.progress,
                'download_speed': t.download_speed,
                'upload_speed': t.upload_speed,
                'peers_count': t.peers_count,
                'stats': t.stats,
            })
    return flask.jsonify(response)

@bp.route('/torrent/<info_hash>', methods=['DELETE'])
def remove_torrent(info_hash):
    try:
        bt.torrent_worker.remove_torrent(info_hash, delete_files=True)
    except bt.TorrentClientError: 
        flask.abort(404)
        
    return ('', 200)

# ---------
# Search
# ---------


@bp.route('/search')
def search():
    query = flask.request.args.get("query")
    if not query:
        flask.abort(400)
    if is_info_hash(query):
        release = get_object_or_404(Release, (Release.info_hash==query.lower()))
        return flask.redirect(flask.url_for('.series_detail', series_id=release.episode.series.id, view="list", _anchor=f"r{release.info_hash}"))
    else:
        series_ids = [series.rowid for series in queries.search_series(
            sanitize_query(query))]
        series = queries.get_series_with_ids(series_ids)
        if len(series) == 1:
            return flask.redirect(flask.url_for('.series_detail', series_id=series[0].id))        
        else:
            return flask.render_template("search_results.html", found_series=series, search_query=query)


def is_info_hash(value):
    return RE_INFO_HASH.match(value)


@bp.route('/suggest')
def suggest():
    query = flask.request.args.get("query")
    if not query:
        flask.abort(400)
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
    series = get_object_or_404(Series, (Series.id == series_id))
    return _series_detail(series)


def _series_detail(series):
    #resolution = flask.request.args.get("resolution", type=int, default=0) or flask.request.cookies.get('resolution', type=int, default=0)
    resolution = flask.request.args.get("resolution", type=int, default=0)
    #size_sorting = flask.request.args.get("size", default="") or flask.request.cookies.get('size', default="")
    size_sorting = flask.request.args.get("size", default="")
    episode_sorting = flask.request.args.get("episode", default="asc")
    view_layout = flask.request.args.get("view", default="grid")
    today = date.today()
    series_subquery = queries.get_series_subquery()
    release_cte = queries.release_cte(resolution, size_sorting)
    if resolution or size_sorting:
        episodes_query = (Episode.select(Episode, Release, Torrent)
                          .join(Release)
                          .join(Torrent, JOIN.LEFT_OUTER)
                          .switch(Episode)
                          .join(Series)
                          .join(series_subquery, on=(
                              series_subquery.c.id == Series.id))
                          .join(release_cte, on=(Release.id == release_cte.c.release_id))
                          .where((Episode.series == series.id) &
                                 # Episodes from last 2 seasons only
                                 (series_subquery.c.max_season - Episode.season < MAX_SEASONS) 
                                 )
                          .order_by(Episode.season.desc(), Episode.number if episode_sorting == "asc" else Episode.number.desc())
                          .with_cte(release_cte))
    else:
        # Unfiltered
        episodes_query = (Episode.select(Episode, Release, Torrent)
                          .join(Release, JOIN.LEFT_OUTER)
                          .join(Torrent, JOIN.LEFT_OUTER)
                          .switch(Episode)
                          .join(Series)
                          .join(series_subquery, on=(
                              series_subquery.c.id == Series.id))
                          .where((Episode.series == series.id) &
                                 # Episodes from last 2 seasons only
                                 (series_subquery.c.max_season - Episode.season < MAX_SEASONS) 
                                 )
                          .order_by(Episode.season.desc(), Episode.number if episode_sorting == "asc" else Episode.number.desc(), Release.seeders.desc()))

    # Group by season number
    seasons_episodes = groupby(episodes_query, key=attrgetter('season'))
    series_tags = queries.get_series_tags(series) 

    response = flask.make_response(flask.render_template("series_detail.html", 
                                                         allow_downloads=True if bt.torrent_worker else False,
                                                         series=series, 
                                                         series_tags=series_tags, 
                                                         seasons_episodes=seasons_episodes, 
                                                         today=today, 
                                                         resolution=resolution, 
                                                         resolution_options=RESOLUTION_OPTIONS, 
                                                         size=size_sorting, 
                                                         size_options=SIZE_OPTIONS,
                                                         episode_sorting=episode_sorting,
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
    release = (Release.select(Release, Torrent)
               .join(Torrent, JOIN.LEFT_OUTER).where(Release.id == release_id).get_or_none())
    return flask.render_template("_release_detail.html", 
                                 utc_now=datetime.now(timezone.utc), 
                                 release=release, 
                                 allow_downloads=True if bt.torrent_worker else False)

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

@bp.route('/settings')
def settings():
    return flask.render_template("_settings.html", 
                                 download_dir=app.config.get('TORRENT_DOWNLOAD_DIR', ''),
                                 max_download_rate=app.config.get('TORRENT_MAX_DOWNLOAD_RATE', ''),                                 
                                 max_upload_rate=app.config.get('TORRENT_MAX_UPLOAD_RATE', ''),        
                                 port=app.config.get('TORRENT_PORT', bt.TORRENT_DEFAULT_PORT),                         
                                 udp_timeout=5, 
                                 max_scraping_interval=90)


# ---------
# Sync database
# ---------

@bp.route('/sync/events')
def sync_events():    
    def stream():
        # Return a message queue
        messages = announcer.listen()
        while True:
            # Blocks until a new message arrives
            msg = messages.get()
            if announcer.is_close_message(msg):
                break
            yield msg
    return flask.Response(stream(), mimetype='text/event-stream')

# ---------
# System status
# ---------

@bp.route('/status')
def system_status():
    log_rows = SyncLog.select().order_by(SyncLog.timestamp.desc()).limit(MAX_LOG_ROWS)
    chart_query = Release.raw(f'SELECT DATE(added_on) AS release_date, COUNT(id) AS release_count FROM `release` GROUP BY release_date ORDER BY release_date DESC LIMIT {MAX_CHART_DAYS}')
    # Filter out trackers that will likely never reply correctly
    trackers = Tracker.select().where((Tracker.status << models.TRACKERS_ALIVE)).order_by(Tracker.status, Tracker.url)
    torrents = (Torrent.select(Torrent, Release, Episode, Series)
                .join(Release)
                .join(Episode)
                .join(Series)
                .where(Torrent.status << [models.TORRENT_ADDED, models.TORRENT_GOT_METADATA])
                .order_by(Torrent.added_on.desc()))    
    max_last_scraped_on = (Tracker.select(fn.Max(Tracker.last_scraped_on).alias("max_last_scraped_on"))
                           .where((Tracker.status << [models.TRACKER_OK, models.TRACKER_TIMED_OUT]))
                           .scalar())
    return flask.render_template("status.html", 
                                 log_rows=log_rows, 
                                 torrents=torrents, 
                                 trackers=trackers, 
                                 chart=chart_query, 
                                 max_chart_days=MAX_CHART_DAYS, 
                                 max_log_rows=MAX_LOG_ROWS, 
                                 max_last_scraped_on=max_last_scraped_on,
                                 torrent_running=bt.torrent_worker and bt.torrent_worker.is_alive(),
                                 torrent_port=app.config.get('TORRENT_PORT', ''))


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