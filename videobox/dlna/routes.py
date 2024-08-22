from datetime import datetime, date, timezone
from itertools import groupby
import re
import flask
#from playhouse.flask_utils import PaginatedQuery, get_object_or_404
import videobox
import videobox.models as models
#from videobox.models import Series, Episode, Release, Tag, SeriesTag, SyncLog, Tracker
from . import bp

@bp.route('/dlna')
def test():
    return ('OK', 200, {})