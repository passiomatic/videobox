'''
DLNA blueprint
'''

from flask import Blueprint

bp = Blueprint('dlna', __name__)

# Make routes importable directly from the blueprint 
from videobox.dlna import routes  # noqa