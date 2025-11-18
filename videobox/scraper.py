# See here for BitTorrent UDP scraping:  
#  https://www.bittorrent.org/beps/bep_0015.html
#  https://www.bittorrent.org/beps/bep_0041.html

from datetime import datetime, timedelta, timezone
import time
from urllib.parse import urlparse, parse_qs
from peewee import *
from flask import current_app as app
import videobox.models as models
import videobox.bt as bt
from videobox.models import Series, Episode, Release, Tracker

MAX_SEASONS = 2 
MIN_SCRAPING_INTERVAL = 1/24*3  # Days
MAX_SCRAPING_INTERVAL = 60      # Days
NEXT_RETRY_DAYS = 3      # Days

def make_series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))

def get_releases(max_releases=None):
    since_datetime = datetime.now(timezone.utc) - timedelta(days=MAX_SCRAPING_INTERVAL)
    series_subquery = make_series_subquery()
    return (Release.select(Release)
            .join(Episode)
            .join(Series)
            .join(series_subquery, on=(
                series_subquery.c.id == Series.id))
            # Do not bother to scrape releases from old seasons
            .where((series_subquery.c.max_season-Episode.season < MAX_SEASONS) & 
                   (Release.added_on >= since_datetime) & 
                   #Torrent.status.in_([TORRENT_ADDED, TORRENT_DOWNLOADING])
                   # Sqlite 'now' uses UTC, see https://www.sqlite.org/lang_datefunc.html
                   (fn.JulianDay('now') - fn.JulianDay(Release.last_updated_on) >
                    (fn.Threshold(fn.JulianDay('now') - fn.JulianDay(Release.added_on)))))
            # Scrape recent releases first
            .order_by(Release.added_on.desc())
            .limit(max_releases))

def scrape_releases(max_releases=None): 
    start = time.time()
    releases = get_releases(max_releases)
    #trackers = collect_trackers(releases)
    #models.save_trackers(app, [{'url': tracker} for tracker in trackers])
    # Contact less frequently those trackers which return fatal errors
    print("Update swarm information... ", end="", flush=True)
    # Remove TZ or Peewee will save it as string in SQLite
    #utc_now = datetime.now(timezone.utc).replace(tzinfo=None)    
    for release in releases:
        bt.scraper_worker.add_torrent(release)
    #bt.scraper_worker.pause()

    end = time.time()
    #app.logger.info(f"Scraped {len(scraped_torrents)} of {len(releases)} releases in {end-start:.1f}s.")
    #print(f"done, updated {len(scraped_torrents)} torrents.")


def get_magnet_uri_trackers(magnet_uri):
    pieces = urlparse(magnet_uri)
    if pieces.scheme != 'magnet':
        raise ValueError(f"Invalid valid magnet link {magnet_uri}")
    data = parse_qs(pieces.query)
    return map(str.lower, data['tr'])

def get_scrape_threshold(value):
    # Normalise (0, max) range to (0, 1) and use a quad function,
    #   see https://easings.net/#easeInQuad
    value = 1 - (MAX_SCRAPING_INTERVAL-value) / MAX_SCRAPING_INTERVAL
    return max(MIN_SCRAPING_INTERVAL, value*value*MAX_SCRAPING_INTERVAL)

def collect_trackers(releases):
    trackers = {}
    for release in releases:
        try:
            tracker_urls = get_magnet_uri_trackers(release.magnet_uri)
        except ValueError as ex:
            app.logger.debug(f"{ex}, skipped")
            continue            
        # Group all torrents by their tracker URL's, 
        #   to minimize newtwork calls
        for url in tracker_urls:
            trackers.setdefault(url, []).append(release.info_hash)
    return trackers