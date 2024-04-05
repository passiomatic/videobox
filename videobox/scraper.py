# See here for UDP scraping:  https://www.bittorrent.org/beps/bep_0015.html
# Adapted from https://github.com/erindru/m2t/blob/master/m2t/scraper.py

from operator import itemgetter
import binascii, urllib, socket, random, struct
from datetime import datetime, timedelta, timezone
import time
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.error
from peewee import *
from flask import current_app as app
from videobox.models import Series, Episode, Release

UDP_TIMEOUT = 5
MAX_TORRENTS = 74  # UDP limit 

PROTOCOL_ID = 0x41727101980
ACTION_CONNECT = 0x0
ACTION_SCRAPE = 0x2
ACTION_ERROR = 0x3

class UnknownTrackerScheme(RuntimeError):
    pass

def scrape_tracker(tracker, hashes):
    """
    Returns the list of seeds, peers and downloads a torrent info_hash has, according to the specified tracker

    Args:
        tracker (str): The announce url for a tracker, usually taken directly from the torrent metadata
        hashes (list): A list of torrent info_hash's to query the tracker for

    Returns:
        A dict of dicts. The key is the torrent info_hash's from the 'hashes' parameter,
        and the value is a dict containing "seeds", "peers", "complete" and "tracker".
        Eg:
        {
            "2d88e693eda7edf3c1fd0c48e8b99b8fd5a820b2" : { "seeds" : "34", "peers" : "189", "completed" : "10", "tracker": "example.com" },
            "8929b29b83736ae650ee8152789559355275bd5c" : { "seeds" : "12", "peers" : "0", "completed" : "290", "tracker": "example.net" }
        }
    """
    tracker = tracker.lower()
    parsed = urlparse(tracker)	
    if parsed.scheme == "udp":
        return scrape_udp(parsed, hashes)
    else:
        raise UnknownTrackerScheme(f"Unknown tracker scheme {parsed.scheme.upper()}")	

def scrape_udp(parsed_tracker, hashes):
    app.logger.debug(f"Scraping {parsed_tracker.geturl()} for {len(hashes)} hashes")
    if len(hashes) > MAX_TORRENTS:
        raise RuntimeError(f"Only {MAX_TORRENTS} hashes can be scraped on a UDP tracker")
    transaction_id = "\x00\x00\x04\x12\x27\x10\x19\x70"
    connection_id = "\x00\x00\x04\x17\x27\x10\x19\x80"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)
    conn = (socket.gethostbyname(parsed_tracker.hostname), parsed_tracker.port)

    req, transaction_id = udp_create_connection_request()
    #try:
    sock.sendto(req, conn)
    # except PermissionError:
    #     raise RuntimeError(f"Don't have permission to send UDP data to {conn}, skipped") 

    buf, _ = sock.recvfrom(2048)
    connection_id = udp_parse_connection_response(buf, transaction_id)

    # Scrape away
    req, transaction_id = udp_create_scrape_request(connection_id, hashes)
    sock.sendto(req, conn)
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
        raise RuntimeError(f"Error while trying to get a connection response: {error}")
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
                "seeds": seeds, 
                "peers": leeches, 
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
    return int(random.randrange(0, 255))

def series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))

def get_releases_within_interval(interval):
    min_datetime = datetime.now(timezone.utc) - timedelta(days=interval)
    #app.logger.info(f"Start scraping releases added since {min_datetime.isoformat()}...")
    subquery = series_subquery()
    return (Release.select()
            .join(Episode)
            .join(Series)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((subquery.c.max_season-Episode.season < 2) & (Release.added_on >= min_datetime))
            .order_by(Release.added_on))

def get_releases_with_ids(release_ids):
    #min_datetime = datetime.now(timezone.utc) - timedelta(days=interval)
    #app.logger.info(f"Start scraping releases added since {min_datetime.isoformat()}...")
    subquery = series_subquery()
    return (Release.select()
            .join(Episode)
            .join(Series)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            # Do not bother to scrape releases from old seasons
            .where((subquery.c.max_season-Episode.season < 2) & (Release.id << release_ids))
            .order_by(Release.added_on))


def get_magnet_uri_trackers(value):
    parsed_magnet_uri = urlparse(value)
    if parsed_magnet_uri.scheme != 'magnet':
        raise ValueError(f"Invalid valid magnet link {value}")
    data = parse_qs(parsed_magnet_uri.query)
    return map(str.lower, data['tr'])


def scrape_releases(all_releases): 

    start = time.time()

    trackers = {}
    for release in all_releases:
        tracker_urls = get_magnet_uri_trackers(release.magnet_uri)
        for url in tracker_urls:
            if url in trackers:
                trackers[url].append(release.info_hash)
            else:
                trackers[url] = [release.info_hash]

    app.logger.info(f"Collected {len(trackers)} unique trackers")

    scraped_torrents = {}
    for tracker_url, releases in trackers.items():
        try:
            torrents = {}
            for chunked_releases in chunked(releases, MAX_TORRENTS):
                torrents.update(scrape_tracker(tracker_url, chunked_releases))
        except UnknownTrackerScheme as ex:
            app.logger.debug(ex)
            continue
        except urllib.error.URLError:
            app.logger.debug(f"Request to {tracker_url} was refused, skipped")
            continue
        except RuntimeError as ex:
            app.logger.debug(f"Request to {tracker_url} gave an exception ({ex}), skipped")
            continue
        except socket.gaierror:
            app.logger.debug(f"{tracker_url} name or service not know, skipped")
            continue
        except socket.timeout:
            app.logger.debug(f"{tracker_url} timed out, skipped")
            continue

        # Group scrape data by info_hash
        for info_hash, data in torrents.items():
            if info_hash in scraped_torrents:
                scraped_torrents[info_hash].append(data)
            else:
                scraped_torrents[info_hash] = [data]            

    utc_now = datetime.now(timezone.utc)
    for info_hash, all_data in scraped_torrents.items():
        # Get best seeds result for each torrent
        data = max(all_data, key=itemgetter("seeds"))
        release = Release.get(info_hash=info_hash)
        app.logger.debug(f"Scraped '{release.name}': seeders {release.seeders}->{data['seeds']}, peers {release.leechers}->{data['peers']}, completed {data['completed']}")
        release.seeders = data['seeds']
        release.leechers = data['peers']
        release.completed = data['completed']
        # Remove TZ or Peewee will save it as string in SQLite
        release.last_updated_on = utc_now.replace(tzinfo=None)
        release.save()
        # Update torrent health table
        # TorrentHealth.create(release=release, timestamp=utc_now, seeders=data['seeds'], leechers=data['peers'], complete=data['completed'], tracker=data['tracker'])

    end = time.time()
    app.logger.info(f"Scraped {len(scraped_torrents)} of {len(all_releases)} releases in {end-start:.1f}s.")