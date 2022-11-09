import requests
import configuration 
import logging

TIMEOUT = 15
API_ENDPOINT_URL = "http://videobox.passiomatic.com/2"
USER_AGENT = "Videobox/{0}.{1}.{2} <https://videobox.passiomatic.com/>".format(*configuration.VERSION)

def get_running_series(client_id):
    return get_url("{0}/series/running?client={1}".format(API_ENDPOINT_URL, client_id))

def get_updated_series(client_id, since):    
    return get_url("{0}/series/updated?since={1}&client={2}".format(API_ENDPOINT_URL, since.isoformat(), client_id))

def get_series_with_ids(client_id, ids):
    return get_url("{0}/series?ids={1}&client={2}".format(API_ENDPOINT_URL, ",".join(map(str, ids)), client_id))

def get_episodes_with_ids(client_id, ids):
    return get_url("{0}/episodes?ids={1}&client={2}".format(API_ENDPOINT_URL, ",".join(map(str, ids)), client_id))

def get_releases_with_ids(client_id, ids):
    return get_url("{0}/releases?ids={1}&client={2}".format(API_ENDPOINT_URL, ",".join(map(str, ids)), client_id))

def get_url(url):
    request_headers = {
        'User-Agent': USER_AGENT
    }    
    logging.debug("Quering API endpoint {0}...".format(url))
    return requests.get(url, timeout=TIMEOUT, headers=request_headers)