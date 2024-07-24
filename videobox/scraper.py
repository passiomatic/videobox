# See here for BitTorrent UDP scraping:  
#  https://www.bittorrent.org/beps/bep_0015.html
#  https://www.bittorrent.org/beps/bep_0041.html
# Adapted from https://github.com/erindru/m2t/blob/master/m2t/scraper.py

from operator import itemgetter
import binascii, socket, random, struct
from datetime import datetime, timedelta, timezone
import time
from urllib.parse import urlparse, parse_qs
#import urllib.error
from peewee import *
from flask import current_app as app
import videobox.models as models
from videobox.models import Series, Episode, Release, Tracker

UDP_TIMEOUT = 5
MAX_TORRENTS = 74               # UDP limit 
MAX_SEASONS = 2 
MIN_SCRAPING_INTERVAL = 1/24*3  # Days
MAX_SCRAPING_INTERVAL = 90      # Days
NEXT_RETRY_DAYS = 3      # Days

PROTOCOL_ID = 0x41727101980
ACTION_CONNECT = 0x0
ACTION_SCRAPE = 0x2
ACTION_ERROR = 0x3

class UnknownTrackerScheme(RuntimeError):
    pass

def scrape_tracker(tracker, hashes):
    """
    Returns the list of seeders, leechers and downloads a torrent info_hash has, according to the specified tracker
    """
    parsed = urlparse(tracker.lower())	
    if parsed.scheme == "udp":
        return scrape_udp(parsed, hashes)
    else:
        raise UnknownTrackerScheme(f"Unknown tracker scheme {parsed.scheme.upper()}, skipped")	

def scrape_udp(parsed_tracker, hashes):
    app.logger.debug(f"Scraping {parsed_tracker.geturl()} for {len(hashes)} hashes")
    if len(hashes) > MAX_TORRENTS:
        raise RuntimeError(f"Only {MAX_TORRENTS} hashes can be scraped on a UDP tracker")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)
    conn = (socket.gethostbyname(parsed_tracker.hostname), parsed_tracker.port)

    request, transaction_id = udp_create_connection_request()
    sock.sendto(request, conn)

    buf, _ = sock.recvfrom(2048)
    connection_id = udp_parse_connection_response(buf, transaction_id)

    # Scrape away
    request, transaction_id = udp_create_scrape_request(connection_id, hashes)
    sock.sendto(request, conn)
    buf, _ = sock.recvfrom(2048)
    data = udp_parse_scrape_response(parsed_tracker, buf, transaction_id, hashes)
    return data

def udp_create_connection_request():    	
    transaction_id = udp_get_transaction_id()
    buf = struct.pack("!q", PROTOCOL_ID) # First 8 bytes is a magic constant
    buf += struct.pack("!i", ACTION_CONNECT) # Next 4 bytes is action
    buf += struct.pack("!i", transaction_id) # Next 4 bytes is transaction id
    return (buf, transaction_id)

def udp_parse_connection_response(buf, sent_transaction_id):
    if len(buf) < 16:
        raise RuntimeError(f"Wrong response length getting connection id: {len(buf)}")			
    action = struct.unpack_from("!i", buf)[0] # First 4 bytes is action

    response_transaction_id = struct.unpack_from("!i", buf, 4)[0] # Next 4 bytes is transaction id
    if response_transaction_id != sent_transaction_id:
        raise RuntimeError(f"Transaction ID doesn't match in connection response: expected {sent_transaction_id}, got {response_transaction_id}")

    if action == ACTION_CONNECT:
        connection_id = struct.unpack_from("!q", buf, 8)[0] # Unpack 8 bytes from byte 8, should be the connection_id
        return connection_id
    elif action == ACTION_ERROR:		
        error = struct.unpack_from("!s", buf, 8)
        raise RuntimeError(f"Error {error} while trying to get a connection response")
    else:
        raise RuntimeError(f"Unknown action value: {action}")

def udp_create_scrape_request(connection_id, hashes):
    transaction_id = udp_get_transaction_id()
    buf = struct.pack("!q", connection_id) # First 8 bytes is connection id
    buf += struct.pack("!i", ACTION_SCRAPE) # Next 4 bytes is action 
    buf += struct.pack("!i", transaction_id) # Followed by 4 byte transaction id

    # From here on, there is a list of info_hashes. They are packed as char[]
    for hash in hashes:		
        hex_repr = binascii.a2b_hex(hash)
        buf += struct.pack("!20s", hex_repr)
    return (buf, transaction_id)

def udp_parse_scrape_response(parsed_tracker, buf, sent_transaction_id, hashes):	
    if len(buf) < 16:
        raise RuntimeError(f"Wrong response length while scraping: {len(buf)}")	

    action = struct.unpack_from("!i", buf)[0] # First 4 bytes is action
    response_transaction_id = struct.unpack_from("!i", buf, 4)[0] # Next 4 bytes is transaction id	
    if response_transaction_id != sent_transaction_id:
        raise RuntimeError(f"Transaction ID doesn't match in scrape response: expected {sent_transaction_id}, got {response_transaction_id}")
    if action == ACTION_SCRAPE:
        response = {}
        offset = 8
        # Next 4 bytes after action is transaction_id, so data doesn't start till byte 8		
        for hash in hashes:
            try: 
                seeds = struct.unpack_from("!i", buf, offset)[0]
                offset += 4
                completed = struct.unpack_from("!i", buf, offset)[0]
                offset += 4
                leeches = struct.unpack_from("!i", buf, offset)[0]
                offset += 4			
            except struct.error:
                raise RuntimeError("Error while unpacking scrape response from tracker")
            response[hash] = {
                "seeders": seeds, 
                "leechers": leeches, 
                "completed": completed, 
                'tracker': parsed_tracker.hostname
            }
        return response
    elif action == ACTION_ERROR:
        # Error occured, try and extract the error string
        error = struct.unpack_from("!s", buf, 8)
        raise RuntimeError(f"Error while scraping: {error}")
    else:
        raise RuntimeError(f"Unknown action value: {action}")

def udp_get_transaction_id():
    return random.randint(0, 255)

def make_series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))

def get_releases():
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
                   # Sqlite 'now' uses UTC, see https://www.sqlite.org/lang_datefunc.html
                   (fn.JulianDay('now') - fn.JulianDay(Release.last_updated_on) >
                    (fn.Threshold(fn.JulianDay('now') - fn.JulianDay(Release.added_on)))))
            # Scrape recent releases first
            .order_by(Release.added_on.desc()))

def scrape_releases(): 
    start = time.time()
    releases = get_releases()
    trackers = collect_trackers(releases)
    models.save_trackers(app, [{'url': tracker} for tracker in trackers])
    # Contact less frequently those trackers which return fatal errors
    next_attempt_days = Case(Tracker.status, (
        (models.TRACKER_PROTOCOL_ERROR, NEXT_RETRY_DAYS),
        (models.TRACKER_DNS_ERROR, NEXT_RETRY_DAYS)), 0)
    candidate_trackers = [tracker.url for tracker in Tracker.select().where((Tracker.last_scraped_on == None) | (fn.JulianDay('now') - fn.JulianDay(Tracker.last_scraped_on) >= next_attempt_days))]
    app.logger.info(f"Start scraping {len(candidate_trackers)} trackers...")
    # Remove TZ or Peewee will save it as string in SQLite
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)    
    scraped_torrents = {}
    for tracker_url, info_hashes in trackers.items():
        if tracker_url not in candidate_trackers:
            continue
        status = models.TRACKER_PROTOCOL_ERROR
        try:
            torrents = {}
            for chunked_info_hashes in chunked(info_hashes, MAX_TORRENTS):
                torrents.update(scrape_tracker(tracker_url, chunked_info_hashes))
                # Do not flood server with requests
                time.sleep(0.75)
            status = models.TRACKER_OK
        except UnknownTrackerScheme as ex:
            app.logger.debug(ex)
            continue
        except socket.gaierror:
            app.logger.debug(f"{tracker_url} name or service is not know, skipped")
            status = models.TRACKER_DNS_ERROR
            continue
        except ConnectionRefusedError:
            app.logger.debug(f"Connection to {tracker_url} was refused, skipped")
            continue
        except RuntimeError as ex:
            app.logger.debug(f"Request to {tracker_url} gave an exception ({ex}), skipped")
            continue
        except socket.timeout:
            app.logger.debug(f"Request to {tracker_url} timed out, skipped")
            status = models.TRACKER_TIMED_OUT
            # Do not skip, but collect as much scraped data as possible
        finally:
            Tracker.update(last_scraped_on=utc_now, status=status).where(Tracker.url == tracker_url).execute()

        # Group scraped data by info_hash
        for info_hash, data in torrents.items():
            scraped_torrents.setdefault(info_hash, []).append(data)

    for info_hash, all_data in scraped_torrents.items():
        # Get best seeds result for each torrent
        data = max(all_data, key=itemgetter("seeders"))
        Release.update(seeders=data['seeders'], 
                       leechers=data['leechers'], 
                       completed=data['completed'],
                       last_updated_on=utc_now).where(Release.info_hash == info_hash).execute()
    end = time.time()
    app.logger.info(f"Scraped {len(scraped_torrents)} of {len(releases)} releases in {end-start:.1f}s.")


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