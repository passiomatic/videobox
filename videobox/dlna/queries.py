
import videobox.models as models
from videobox.models import Series, Episode, Release, Torrent

def downloaded_series(): 
    return (Series.select(Series)
            .join(Episode)
            .join(Release)
            .join(Torrent)
            .where(Torrent.status == models.TORRENT_DOWNLOADED))