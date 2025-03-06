from datetime import datetime, date, timezone
from operator import attrgetter
from itertools import groupby
from pathlib import Path
import re
import flask
from flask import current_app as app
from peewee import fn, JOIN
from playhouse.flask_utils import PaginatedQuery, get_object_or_404
import videobox
import videobox.bt as bt
import videobox.models as models
import videobox.scraper as scraper
from videobox.models import Series, Episode, Release, Tag, SeriesTag, SyncLog, Tracker, Torrent
from . import bp
from .announcer import announcer
from . import queries

MAX_CHART_DAYS = 30 
MAX_TOP_TAGS = 8
MIN_SEEDERS = 1
MAX_SEASONS = 2
MAX_LOG_ROWS = 5
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
    "any": "Any",
    "asc": "Smallest",
    "desc": "Largest",
}
RE_INFO_HASH = re.compile(r"^[0-9a-fA-F]{40}$")
RESOLUTION_FILTER_COOKIE = 'filter-video-resolution'
SIZE_SORTING_COOKIE = 'size-sorting'
EPISODE_SORTING_COOKIE = "episode-sorting"

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
        chart_query = Release.raw(f'SELECT DATE(added_on) AS release_date, COUNT(id) AS release_count FROM `release` GROUP BY release_date ORDER BY release_date DESC LIMIT {MAX_CHART_DAYS}')
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
                                     chart=chart_query,
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
        bt.torrent_worker.add_torrent(release)
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
                'state': t.state_code
            })
    return flask.jsonify(response)

@bp.route('/torrent/<info_hash>', methods=['DELETE'])
def remove_torrent(info_hash):
    did_remove = bt.torrent_worker.remove_torrent(info_hash, delete_files=False)
        
    return ('', 200) if did_remove else flask.abort(404)

@bp.route('/downloads')
def downloads():
    torrents = (Torrent.select(Torrent, Release, Episode, Series)
                .join(Release)
                .join(Episode)
                .join(Series)
                .where(Torrent.status << [models.TORRENT_ADDED, models.TORRENT_DOWNLOADING, models.TORRENT_DOWNLOADED])
                .order_by(Torrent.added_on.desc()))    
    return flask.render_template("downloads.html", 
                                 utc_now=datetime.now(timezone.utc),
                                 torrents=torrents, 
                                 torrent_running=torrent_running())

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
    series_sorting = flask.request.args.get("sort", default="popularity")
    query = queries.get_series_for_tag(tag, series_sorting)
    paginated_series = PaginatedQuery(query, paginate_by=SERIES_CARDS_PER_PAGE, page_var="page", check_bounds=True)
    if page == 1:
        return flask.render_template("tag_detail.html", tag=tag, series=paginated_series, page=page, series_count=query.count(), series_sorting=series_sorting)
    else:
        # For async requests
        return flask.render_template("_tag-card-grid.html", tag=tag, series=paginated_series, page=page, series_sorting=series_sorting)

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
    # Check request value first
    resolution_filter = flask.request.args.get("resolution", type=int, default=-1)
    if resolution_filter < 0:
        resolution_filter = flask.request.cookies.get(RESOLUTION_FILTER_COOKIE, type=int, default=0)
    size_sorting = flask.request.args.get("size", default="")
    if not size_sorting:
        size_sorting = flask.request.cookies.get(SIZE_SORTING_COOKIE, default="any")
    episode_sorting = flask.request.args.get("episode", default="")
    if not episode_sorting:
        episode_sorting = flask.request.cookies.get(EPISODE_SORTING_COOKIE, default="asc")
    view_layout = flask.request.args.get("view", default="grid")
    is_async = flask.request.args.get("async", type=int, default=0) == 1
    today = date.today()
    series_subquery = queries.get_series_subquery()
    release_cte = queries.release_cte(resolution_filter, size_sorting)
    if resolution_filter or size_sorting != "any":
        # Filtered
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

    filter_message = 'Showing torrents '
    if resolution_filter > 0:
        filter_message += f'with {resolution_filter}p video resolution and '
    else:
        filter_message += 'with any video resolution and '
    if size_sorting == 'asc':        
        filter_message += 'smallest file sizes, regardless of seeded numbers' 
    elif size_sorting == 'desc':
        filter_message += 'largest file sizes, regardless of seeded numbers'
    else:
        filter_message += 'ranked by seeded numbers'

    # Group by season number
    seasons_episodes = groupby(episodes_query, key=attrgetter('season'))
    series_tags = queries.get_series_tags(series) 
    template = "_episodes.html" if is_async else "series_detail.html"
    response = flask.make_response(flask.render_template(template, 
                                                         allow_downloads=True if bt.torrent_worker else False,
                                                         series=series, 
                                                         series_tags=series_tags, 
                                                         seasons_episodes=seasons_episodes, 
                                                         today=today, 
                                                         resolution=resolution_filter, 
                                                         resolution_options=RESOLUTION_OPTIONS, 
                                                         size=size_sorting, 
                                                         size_options=SIZE_OPTIONS,
                                                         episode_sorting=episode_sorting,
                                                         view_layout=view_layout,
                                                         torrent_running=torrent_running(),
                                                         filter_message=filter_message))
    if resolution_filter > 0:
        response.set_cookie(RESOLUTION_FILTER_COOKIE, str(resolution_filter))
    else:
        response.delete_cookie(RESOLUTION_FILTER_COOKIE)
    if size_sorting != 'any':
        response.set_cookie(SIZE_SORTING_COOKIE, size_sorting)    
    else:
        response.delete_cookie(SIZE_SORTING_COOKIE)
    if episode_sorting != 'asc':
        response.set_cookie(EPISODE_SORTING_COOKIE, episode_sorting)
    else:
        response.delete_cookie(EPISODE_SORTING_COOKIE)

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
    tracker_urls = list(scraper.get_magnet_uri_trackers(release.magnet_uri))
    trackers = Tracker.select().where(Tracker.url << tracker_urls).order_by(Tracker.status, Tracker.url)
    return flask.render_template("_release_detail.html", 
                                 utc_now=datetime.now(timezone.utc), 
                                 release=release, 
                                 trackers=trackers,
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
                                 enabled=app.config.get('TORRENT_ENABLED', False),
                                 download_dir=app.config.get('TORRENT_DOWNLOAD_DIR', '') or Path.home(),
                                 max_download_rate=app.config.get('TORRENT_MAX_DOWNLOAD_RATE', '') or '',                                 
                                 max_upload_rate=app.config.get('TORRENT_MAX_UPLOAD_RATE', '') or '',        
                                 port=app.config.get('TORRENT_PORT', bt.TORRENT_DEFAULT_PORT))

@bp.route('/settings', methods=['POST'])
def settings_update():
    enabled = flask.request.form.get("enabled") == 'true'
    download_dir = flask.request.form.get("download_dir", '')
    max_download_rate = flask.request.form.get("max_download_rate", 0, type=int)
    max_upload_rate = flask.request.form.get("max_upload_rate", 0, type=int)
    port = flask.request.form.get("port", bt.TORRENT_DEFAULT_PORT, type=int)

    app.config['TORRENT_ENABLED'] = enabled
    app.config['TORRENT_DOWNLOAD_DIR'] = download_dir
    app.config['TORRENT_MAX_DOWNLOAD_RATE'] = max_download_rate
    app.config['TORRENT_MAX_UPLOAD_RATE'] = max_upload_rate
    app.config['TORRENT_PORT'] = port

    return ('', 200)

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
                .where(Torrent.status << [models.TORRENT_ADDED, models.TORRENT_DOWNLOADING, models.TORRENT_DOWNLOADED])
                .order_by(Torrent.added_on.desc()))    
    max_last_scraped_on = (Tracker.select(fn.Max(Tracker.last_scraped_on).alias("max_last_scraped_on"))
                           .where((Tracker.status << [models.TRACKER_OK, models.TRACKER_TIMED_OUT]))
                           .scalar())
    torrent_port = bt.torrent_worker.session.listen_port() if bt.torrent_worker else ''
    return flask.render_template("status.html", 
                                 utc_now=datetime.now(timezone.utc),
                                 log_rows=log_rows, 
                                 torrents=torrents, 
                                 trackers=trackers, 
                                 chart=chart_query, 
                                 max_chart_days=MAX_CHART_DAYS, 
                                 max_log_rows=MAX_LOG_ROWS, 
                                 max_last_scraped_on=max_last_scraped_on,
                                 torrent_running=torrent_running(),
                                 torrent_port=torrent_port)


# ---------
# Helpers
# ---------

def torrent_running():
    return bt.torrent_worker and bt.torrent_worker.is_alive() and bt.torrent_worker.session.is_listening()

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