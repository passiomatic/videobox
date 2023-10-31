'''
Web UI blueprint
'''

from flask import Blueprint

bp = Blueprint('main', __name__)

# Make routes importable directly from the blueprint 
from videobox.main import routes  # noqa