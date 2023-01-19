import requests
import videobox
import logging

TIMEOUT = 10
API_ENDPOINT_URL = "https://videobox.passiomatic.com/1"
USER_AGENT = "Videobox/{0} <https://videobox.passiomatic.com/>".format(
    videobox.__version__)


def get_running_series(client_id):
    return get_url("{0}/series/running?client={1}".format(API_ENDPOINT_URL, client_id))


def get_updated_series(client_id, since):
    return get_url("{0}/series/updated?since={1}&client={2}".format(API_ENDPOINT_URL, int(since.timestamp()), client_id))


def get_series_with_ids(client_id, ids):
    return get_url("{0}/series?ids={1}&client={2}".format(API_ENDPOINT_URL, make_ids(ids), client_id))


def get_series_tags_for_ids(client_id, ids):
    return get_url("{0}/series-tags?ids={1}&client={2}".format(API_ENDPOINT_URL, make_ids(ids), client_id))


def get_episodes_with_ids(client_id, ids):
    return get_url("{0}/episodes?ids={1}&client={2}".format(API_ENDPOINT_URL, make_ids(ids), client_id))


def get_releases_with_ids(client_id, ids):
    return get_url("{0}/releases?ids={1}&client={2}".format(API_ENDPOINT_URL, make_ids(ids), client_id))


def make_ids(ids):
    return ",".join(map(str, ids))


def get_url(url):
    request_headers = {
        'User-Agent': USER_AGENT
    }
    logging.debug(f"Quering API endpoint {url}...")
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)