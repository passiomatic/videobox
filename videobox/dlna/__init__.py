'''
DLNA blueprint

Implements a subset of MediaServer:1 from 
  http://upnp.org/specs/av/UPnP-av-MediaServer-v1-Device.pdf

'''

from flask import Blueprint

bp = Blueprint('dlna', __name__)

# Make routes importable directly from the blueprint 
from videobox.dlna import routes  # noqa