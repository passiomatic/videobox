from flask import current_app
from urllib.parse import urljoin
import videobox

TIMEOUT = 10
API_VERSION = 4
DEFAULT_API_BASE_URL = "https://www.videobox.passiomatic.com/"
USER_AGENT = f"Videobox/{videobox.__version__} (https://pypi.org/project/videobox/)"

# Full import


def get_all_tags(session, client_id):
    return get_url(session, f"{API_VERSION}/tags/all?client={client_id}")


def get_all_series(session, client_id):
    return get_url(session, f"{API_VERSION}/series/all?client={client_id}")


def get_all_series_tags(session, client_id):
    return get_url(session, f"{API_VERSION}/series-tags/all?client={client_id}")


def get_all_episodes(session, client_id):
    return get_url(session, f"{API_VERSION}/episodes/all?client={client_id}")


def get_all_releases(session, client_id):
    return get_url(session, f"{API_VERSION}/releases/all?client={client_id}")


# Sync


def get_updated_series(session, client_id, since):
    return get_url(session, f"{API_VERSION}/series/updated?since={int(since.timestamp())}&client={client_id}")


def get_tags_with_ids(session, client_id, ids):
    return get_url(session, f"{API_VERSION}/tags?ids={make_ids(ids)}&client={client_id}")


def get_series_with_ids(session, client_id, ids):
    return get_url(session, f"{API_VERSION}/series?ids={make_ids(ids)}&client={client_id}")


def get_series_tags_for_ids(session, client_id, ids):
    return get_url(session, f"{API_VERSION}/series-tags?ids={make_ids(ids)}&client={client_id}")


def get_episodes_with_ids(session, client_id, ids):
    return get_url(session, f"{API_VERSION}/episodes?ids={make_ids(ids)}&client={client_id}")


def get_releases_with_ids(session, client_id, ids):
    return get_url(session, f"{API_VERSION}/releases?ids={make_ids(ids)}&client={client_id}")


def make_ids(ids):
    return ",".join(map(str, ids))


def get_url(session, path):
    request_headers = {
        'User-Agent': USER_AGENT
    }
    url = urljoin(current_app.config.get('API_BASE_URL', DEFAULT_API_BASE_URL), path)
    #current_app.logger.debug(f"Quering API endpoint {url}...")
    return session.get(url, timeout=TIMEOUT, headers=request_headers)
