import requests
from flask import current_app
import videobox

TIMEOUT = 10
API_VERSION = 4
API_ENDPOINT_URL = f"https://videobox.passiomatic.com/{API_VERSION}"
USER_AGENT = f"Videobox/{videobox.__version__} <https://videobox.passiomatic.com/>"


def get_info(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/info.json")


def get_tags(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/tags.json")


def get_series(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/series.json")


def get_series_tags(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/series-tags.json")


def get_episodes(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/episodes.json")


def get_releases(sync_type):
    return get_url(f"{API_ENDPOINT_URL}/{sync_type}/releases.json")


def get_url(url):
    request_headers = {
        'User-Agent': USER_AGENT
    }
    current_app.logger.debug(f"Quering API endpoint {url}...")
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)
