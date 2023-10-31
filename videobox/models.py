import itertools
from datetime import datetime, date, timedelta
from peewee import *
from playhouse.sqlite_ext import FTS5Model, SearchField, RowIDField
from playhouse.flask_utils import FlaskDB
#import sqlite3

# Defer init in app creation
db_wrapper = FlaskDB()

SYNC_STARTED = "S"
SYNC_ERROR = "E"
SYNC_OK = "K"

TAG_GENRE = "G"
TAG_KEYWORD = "K"

class SyncLog(db_wrapper.Model):
    timestamp = TimestampField(utc=True)
    status = CharField(default=SYNC_STARTED)
    description = TextField(default="")

    def __str__(self):
        return f"[{self.status} {self.timestamp}] {self.description}"


def get_last_log():
    """
    Get last successful sync, if any
    """
    return SyncLog.select().where(SyncLog.status == "K").order_by(SyncLog.timestamp.desc()).get_or_none()


class Series(db_wrapper.Model):
    tmdb_id = IntegerField(unique=True)
    imdb_id = CharField(default="")
    name = CharField()
    sort_name = CharField()
    tagline = CharField(default="")
    slug = CharField()
    overview = TextField()
    network = CharField(default="")
    poster_url = CharField(default="")
    fanart_url = CharField(default="")
    vote_average = FloatField(default=0)
    popularity = FloatField(default=0)
    status = FixedCharField(max_length=1)
    language = CharField(max_length=2)
    last_updated_on = DateTimeField(default=datetime.utcnow)

    @property
    def imdb_url(self):
        if self.imdb_id:
            return f"https://www.imdb.com/title/{self.imdb_id}/"
        else:
            return ""

    @property
    def tvdb_url(self):
        return f"https://thetvdb.com/series/{self.slug}"

    def __str__(self):
        return self.name


class SeriesIndex(FTS5Model):
    """
    Full-text search index for series
    """
    rowid = RowIDField()
    name = SearchField()
    content = SearchField() # Contains all other relevant fields

    class Meta:
        database = db_wrapper.database
        options = {'tokenize': 'porter'}


class Tag(db_wrapper.Model):
    slug = CharField()
    name = CharField()
    type = FixedCharField(max_length=1)    

    def __str__(self):
        return self.name


class SeriesTag(db_wrapper.Model):
    series = ForeignKeyField(Series, on_delete="CASCADE")
    tag = ForeignKeyField(Tag, on_delete="CASCADE")

    class Meta:
        primary_key = CompositeKey('series', 'tag')


class Episode(db_wrapper.Model):
    tmdb_id = IntegerField()
    series = ForeignKeyField(Series, backref='episodes', on_delete="CASCADE")
    name = CharField()
    season = SmallIntegerField()
    number = SmallIntegerField()
    aired_on = DateField(null=True)
    overview = TextField(default="")
    last_updated_on = DateTimeField(default=datetime.utcnow)
    thumbnail_url = CharField(default="")

    @property
    def season_episode_id(self):
        return "S{:02}.E{:02}".format(self.season, self.number)

    def __str__(self):
        return f"{self.season_episode_id} '{self.name}'"

    class Meta:
        indexes = (
            (('series', 'season', 'number'), True),
        )


# class EpisodeIndex(FTS5Model):
#     """
#     Full-text search index for episodes
#     """
#     rowid = RowIDField()
#     name = SearchField()
#     overview = SearchField()

#     class Meta:
#         database = db_wrapper.database
#         options = {'tokenize': 'porter'}


class Release(db_wrapper.Model):
    # Enough for BitTorrent 2 SHA-256 hashes
    info_hash = CharField(unique=True, max_length=64)
    # We could change an episode id, so update this FK accordingly
    episode = ForeignKeyField(
        Episode, backref='releases', on_update="CASCADE", on_delete="CASCADE")
    added_on = DateTimeField()
    last_updated_on = DateTimeField()
    size = BigIntegerField()
    magnet_uri = TextField()
    seeders = IntegerField()
    leechers = IntegerField()
    completed = IntegerField()
    name = CharField()
    resolution = SmallIntegerField()

    def __str__(self):
        return self.name


###########
# DB SETUP
###########

def setup():
    db_wrapper.database.create_tables([
        Series,
        SeriesIndex,
        Episode,
        #EpisodeIndex,
        Release,
        Tag,
        SeriesTag,
        SyncLog,
    ], safe=True)