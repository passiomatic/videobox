import requests
from flask import current_app
import videobox

TIMEOUT = 10
API_VERSION = 3
API_ENDPOINT_URL = f"https://www.videobox.passiomatic.com/{API_VERSION}"
USER_AGENT = f"Videobox/{videobox.__version__} (https://videobox.passiomatic.com/)"

# Full import


def get_all_tags(client_id):
    return get_url(f"{API_ENDPOINT_URL}/tags/all?client={client_id}")


def get_all_series(client_id):
    return get_url(f"{API_ENDPOINT_URL}/series/all?client={client_id}")


def get_all_series_tags(client_id):
    return get_url(f"{API_ENDPOINT_URL}/series-tags/all?client={client_id}")


def get_all_episodes(client_id):
    return get_url(f"{API_ENDPOINT_URL}/episodes/all?client={client_id}")


def get_all_releases(client_id):
    return get_url(f"{API_ENDPOINT_URL}/releases/all?client={client_id}")


# Sync


def get_updated_series(client_id, since):
    return get_url(f"{API_ENDPOINT_URL}/series/updated?since={int(since.timestamp())}&client={client_id}")


def get_tags_with_ids(client_id, ids):
    return get_url(f"{API_ENDPOINT_URL}/tags?ids={make_ids(ids)}&client={client_id}")


def get_series_with_ids(client_id, ids):
    return get_url(f"{API_ENDPOINT_URL}/series?ids={make_ids(ids)}&client={client_id}")


def get_series_tags_for_ids(client_id, ids):
    return get_url(f"{API_ENDPOINT_URL}/series-tags?ids={make_ids(ids)}&client={client_id}")


def get_episodes_with_ids(client_id, ids):
    return get_url(f"{API_ENDPOINT_URL}/episodes?ids={make_ids(ids)}&client={client_id}")


def get_releases_with_ids(client_id, ids):
    return get_url(f"{API_ENDPOINT_URL}/releases?ids={make_ids(ids)}&client={client_id}")


def make_ids(ids):
    return ",".join(map(str, ids))


def get_url(url):
    request_headers = {
        'User-Agent': USER_AGENT
    }
    current_app.logger.debug(f"Quering API endpoint {url}...")
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)
