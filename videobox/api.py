import requests
from flask import current_app
import videobox

TIMEOUT = 10
API_VERSION = 4
API_ENDPOINT_URL = f"https://videobox.passiomatic.com/{API_VERSION}"
USER_AGENT = f"Videobox/{videobox.__version__} <https://videobox.passiomatic.com/>"


def get_info(etag=''):
    request_headers = {
        'User-Agent': USER_AGENT,
        'If-None-Match': etag
    }
    url = f"{API_ENDPOINT_URL}/info.json"
    current_app.logger.debug(f"Quering API endpoint {url}...")
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)


def get_tags(quick):
    return get_url("tags.json", quick)


def get_series(quick):
    return get_url("series.json", quick)


def get_series_tags(quick):
    return get_url("series-tags.json", quick)


def get_episodes(quick):
    return get_url("episodes.json", quick)


def get_releases(quick):
    return get_url("releases.json", quick)


def get_url(filename, quick, headers=None):
    request_headers = {
        'User-Agent': USER_AGENT
    }
    if headers:
        request_headers.update(headers)
    sync_type = 'quick' if quick else 'full'
    url = f"{API_ENDPOINT_URL}/{sync_type}/{filename}"
    current_app.logger.debug(f"Quering API endpoint {url}...")
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)
