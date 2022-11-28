import os
from datetime import datetime, date, timedelta
from peewee import *
from playhouse.sqlite_ext import FTS5Model, SearchField, RowIDField
import configuration
from kivy.logger import Logger
import sqlite3

STATUS_WATCHED = "W"
STATUS_IN_PROGRESS = "P"
STATUS_UNWATCHED = "U"

# Defer init
db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class SyncLog(BaseModel):
    timestamp = TimestampField(utc=True)
    status = CharField(default="S")  # S, E, K, C
    description = TextField(default="")

    def __str__(self):
        return f"[{self.status} {self.timestamp}] {self.description}"


class Series(BaseModel):
    tvdb_id = IntegerField(primary_key=True)
    name = CharField()
    sort_name = CharField()
    slug = CharField()
    overview = TextField()
    network = CharField(default="")
    poster_url = CharField(default="")
    fanart_url = CharField(default="")
    # ISO code for matched series language in TVDb
    language = CharField(max_length=2, default="en")
    last_updated_on = DateTimeField(default=datetime.utcnow)

    def __str__(self):
        return self.name


class SeriesIndex(FTS5Model):
    """
    Full-text search index for series
    """
    rowid = RowIDField()
    name = SearchField()
    overview = SearchField()
    network = SearchField()

    class Meta:
        database = db
        options = {'tokenize': 'porter'}


class Tag(BaseModel):
    slug = CharField(primary_key=True)
    name = CharField()

    def __str__(self):
        return self.name


class SeriesTag(BaseModel):
    series = ForeignKeyField(Series, on_delete="CASCADE")
    # We could change a tag slug, so update this FK accordingly
    tag = ForeignKeyField(Tag, on_delete="CASCADE", on_update="CASCADE")

    class Meta:
        indexes = (
            (('series', 'tag'), True),
        )


class Episode(BaseModel):
    tvdb_id = IntegerField(primary_key=True)
    series = ForeignKeyField(
        Series, column_name="series_tvdb_id", backref='episodes', on_delete="CASCADE")
    name = CharField()
    season = SmallIntegerField()
    number = SmallIntegerField()
    aired_on = DateField(null=True)
    overview = TextField(default="")
    last_updated_on = DateTimeField(default=datetime.utcnow)
    thumbnail_url = CharField(default="")

    @property
    def season_episode_id(self):
        return "S{:02}E{:02}".format(self.season, self.number)

    def __str__(self):
        return f"{self.season_episode_id} '{self.name}'"

    class Meta:
        indexes = (
            (('series', 'season', 'number'), True),
        )


class EpisodeIndex(FTS5Model):
    """
    Full-text search index for episodes
    """
    rowid = RowIDField()
    name = SearchField()
    overview = SearchField()

    class Meta:
        database = db
        options = {'tokenize': 'porter'}


class Release(BaseModel):
    # Enough for BitTorrent 2 SHA-256 hashes
    info_hash = CharField(unique=True, max_length=64)
    # We could change an episode id, so update this FK accordingly
    episode = ForeignKeyField(Episode, column_name="episode_tvdb_id",
                              backref='releases', on_update="CASCADE", on_delete="CASCADE")
    added_on = DateTimeField()
    size = BigIntegerField()
    magnet_uri = TextField()
    seeds = IntegerField()
    leeches = IntegerField()
    original_name = CharField()
    last_played_on = DateTimeField(null=True)
    status = CharField(default=STATUS_UNWATCHED, max_length=1)

    def __str__(self):
        return self.original_name

    @property
    def resolution(self):
        if "2160p" in self.original_name.lower():
            return "2160p"
        elif "1080p" in self.original_name.lower():
            return "1080p"
        elif "720p" in self.original_name.lower():
            return "720p"
        else:
            return ""


class Transfer(BaseModel):
    release = ForeignKeyField(Release, unique=True, on_delete="CASCADE")
    path = CharField()
    resume_data = BlobField(null=True)
    added_on = DateTimeField(default=datetime.utcnow)
    
    def __str__(self):
        return self.path


###########
# LOCAL DB QUERIES
###########

def series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias.tvdb_id, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.tvdb_id))


def episode_subquery():
    EpisodeAlias = Episode.alias()
    return (EpisodeAlias.select(EpisodeAlias,  Series.tvdb_id.alias('series_tvdb_id'))
            .join(Series)
            )

# def episode_watched_subquery():
#     EpisodeAlias = Episode.alias()
#     return (EpisodeAlias.select(EpisodeAlias.tvdb_id, fn.Count(Release.status).alias("watched_releases"))
#       .join(Release)
#       .where(Release.status == "W")
#       .group_by(EpisodeAlias.tvdb_id)
#       )


def get_new_series(interval):
    esubquery = episode_subquery()
    since_date = date.today() - timedelta(days=interval)
    return (Series.select(Series, fn.Count(esubquery.c.tvdb_id.distinct()).alias("episode_count"))
            .join(Episode)
            .join(Release)
            .join(esubquery, on=(
                esubquery.c.series_tvdb_id == Series.tvdb_id))
            .where((Episode.number == 1) &
                   (Episode.season == 1) &
            (Episode.aired_on != None) &
            (Episode.aired_on > since_date) &
            (Release.added_on > since_date))
            .order_by(Release.added_on.desc())
            .group_by(Series.tvdb_id)
            )


def get_watched_series():
    esubquery = episode_subquery()
    subquery = series_subquery()
    return (Series.select(Series, fn.Count(esubquery.c.tvdb_id.distinct()).alias("episode_count"))
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.tvdb_id == Series.tvdb_id))
            .join(esubquery, on=(
                esubquery.c.series_tvdb_id == Series.tvdb_id))
            .where((subquery.c.max_season == Episode.season) & (Release.status != STATUS_UNWATCHED))
            .order_by(Release.last_played_on.desc())
            .group_by(Series.tvdb_id)
            )


def get_updated_series(interval):
    subquery = series_subquery()
    return (Series.select(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.tvdb_id == Series.tvdb_id))
            .where((subquery.c.max_season == Episode.season) &
            (Release.added_on > (date.today() - timedelta(days=interval))))
            .order_by(Series.sort_name)
            .group_by(Series.tvdb_id)
            )


def get_featured_series(interval):
    subquery = series_subquery()
    esubquery = episode_subquery()
    return (Series.select(Series, fn.Count(esubquery.c.tvdb_id.distinct()).alias("episode_count"), fn.SUM(Release.seeds).alias("seeds"))
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.tvdb_id == Series.tvdb_id))
            .join(esubquery, on=(
                esubquery.c.series_tvdb_id == Series.tvdb_id))
            .where((subquery.c.max_season == Episode.season)
                   & (Release.added_on > (date.today() - timedelta(days=interval))))
            .order_by(fn.SUM(Release.seeds).desc())
            .group_by(Series.tvdb_id)
            )


def get_series(tvdb_id):
    return Series.get(Series.tvdb_id == tvdb_id)


def get_episode(tvdb_id):
    return Episode.get(Episode.tvdb_id == tvdb_id)


def get_release(id):
    return Release.get(Release.id == id)


def get_release_with_info_hash(info_hash):
    return Release.get(Release.info_hash==info_hash)


def get_tranfers(): 
    return Transfer.select().where(Transfer.resume_data != None)    


def get_episodes_for_series(series):
    # Only the last season episodes, even if not aired yet
    subquery = series_subquery()
    return (Episode.select(Episode, fn.Count(Release.info_hash.distinct()).alias('release_count'))
            .join(Release, JOIN.LEFT_OUTER)
            .switch(Episode)
            .join(Series)
            .join(subquery, on=(
                subquery.c.tvdb_id == Series.tvdb_id))
            .where((Episode.series == series.tvdb_id) & (subquery.c.max_season == Episode.season))
            .group_by(Episode.tvdb_id)
            .order_by(Episode.season, Episode.number))


def get_tags_for_series(series):
    return (Tag
            .select()
            .join(SeriesTag)
            .join(Series)
            .where(Series.tvdb_id == series.tvdb_id))

# def get_releases_for_episode(episode):
#   return (Release.select()
#       .join(Episode)
#       .where((Episode.tvdb_id == episode.tvdb_id))
#       .order_by(Release.seeds))


def mark_release(info_hash, status):
    # try:
    release = Release.get(Release.info_hash == info_hash)
    release.status = status
    #release.last_played_on = datetime.utcnow()
    release.save()
    # except Release.DoesNotExist:
    # pass


def connect(app_dir, shouldSetup=False):
    Logger.debug(f"Using SQLite version {sqlite3.sqlite_version}")
    Logger.debug(f"Full text search 5? {FTS5Model.fts5_installed()}")

    database = os.path.join(app_dir, configuration.DATABASE_FILENAME)
    db.init(database)
    db.connect()
    if shouldSetup:
        setup()


def close():
    db.close()


###########
# LOCAL DB SETUP
###########

def setup():
    db.create_tables([
        Series,
        SeriesIndex,
        Episode,
        EpisodeIndex,
        Release,
        Transfer,
        Tag,
        SeriesTag,
        SyncLog
    ], safe=True)

    if Tag.select().count() == 0:
        for slug, name in configuration.TAGS.items():
            Tag.create(slug=slug, name=name)
