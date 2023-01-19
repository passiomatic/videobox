import os
from datetime import datetime, date, timedelta
from peewee import *
from playhouse.sqlite_ext import FTS5Model, SearchField, RowIDField
import sqlite3
import logging

DATABASE_FILENAME = 'library.db'

# Defer init
db = SqliteDatabase(None)


class SyncLog(db.Model):
    timestamp = TimestampField(utc=True)
    status = CharField(default="S")  # S, E, K
    description = TextField(default="")

    def __str__(self):
        return f"[{self.status} {self.timestamp}] {self.description}"


class Series(db.Model):
    tvdb_id = IntegerField(unique=True)
    imdb_id = CharField(null=True)
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
    overview = SearchField()
    network = SearchField()

    class Meta:
        database = db
        options = {'tokenize': 'porter'}


class Tag(db.Model):
    slug = CharField(primary_key=True)
    name = CharField()

    def __str__(self):
        return self.name


class SeriesTag(db.Model):
    series = ForeignKeyField(Series, on_delete="CASCADE")
    # We could change a tag slug, so update this FK accordingly
    tag = ForeignKeyField(Tag, column_name="tag_slug",
                          on_delete="CASCADE", on_update="CASCADE")

    class Meta:
        indexes = (
            (('series', 'tag'), True),
        )


class Episode(db.Model):
    tvdb_id = IntegerField(unique=True)
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


class Release(db.Model):
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
    peers = IntegerField()
    name = CharField()
    resolution = SmallIntegerField()

    def __str__(self):
        return self.name


###########
# LOCAL DB QUERIES
###########

def get_last_log():
    """
    Get last successful sync, if any
    """
    return SyncLog.select().where(SyncLog.status == "K").order_by(SyncLog.timestamp.desc()).get_or_none()


def series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias.id, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))


def episode_subquery():
    EpisodeAlias = Episode.alias()
    return (EpisodeAlias.select(EpisodeAlias,  Series.id.alias('series_id'))
            .join(Series)
            )


def get_new_series(interval):
    esubquery = episode_subquery()
    since_date = date.today() - timedelta(days=interval)
    return (Series.select(Series, fn.Count(esubquery.c.id.distinct()).alias("episode_count"))
            .join(Episode)
            .join(Release)
            .join(esubquery, on=(
                esubquery.c.series_id == Series.id))
            .where((Episode.number == 1) &
                   (Episode.season == 1) &
            (Episode.aired_on != None) &
            (Episode.aired_on > since_date) &
            (Release.added_on > since_date))
            .order_by(Release.added_on.desc())
            .group_by(Series.id)
            )


def get_running_series(interval):
    subquery = series_subquery()
    return (Series.select(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((subquery.c.max_season == Episode.season) &
            (Release.added_on > (date.today() - timedelta(days=interval))))
            .order_by(Series.sort_name)
            .group_by(Series.id)
            )


def get_featured_series(interval):
    subquery = series_subquery()
    esubquery = episode_subquery()
    return (Series.select(Series, fn.Count(esubquery.c.id.distinct()).alias("episode_count"), fn.SUM(Release.seeders).alias("seeders"))
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .join(esubquery, on=(
                esubquery.c.series_id == Series.id))
            .where((subquery.c.max_season == Episode.season)
                   & (Release.added_on > (date.today() - timedelta(days=interval))))
            .order_by(fn.SUM(Release.seeders).desc())
            .group_by(Series.id)
            )


def search_series(query):
    # return SeriesIndex.search(query, weights={'name': 2.0, 'overview': 0.1, 'network': 0.1}, with_score=True, score_alias='search_score')
    return SeriesIndex.search(query, with_score=True, score_alias='search_score')


def get_series(series_id):
    return Series.get(Series.id == series_id)


def get_episode(episode_id):
    return Episode.get(Episode.id == episode_id)


def get_release(id):
    return Release.get(Release.id == id)


# def get_release_with_info_hash(info_hash):
#     return Release.get(Release.info_hash==info_hash)


def get_episodes_for_series(series, season=None):
    subquery = series_subquery()
    return (Episode.select(Episode, fn.Count(Release.info_hash.distinct()).alias('release_count'))
            .join(Release, JOIN.LEFT_OUTER)
            .switch(Episode)
            .join(Series)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            # .where((Episode.series == series.id) & (subquery.c.max_season == Episode.season))
            .where(Episode.series == series.id)
            .group_by(Episode.id)
            .order_by(Episode.season, Episode.number))


def get_releases_for_series(series_id, season=None, max_resolution=2160):
    if season:
        return (Release.select(Release)
                .join(Episode)
                .where((Episode.series == series_id) & (Episode.season == season) & (Release.resolution <= max_resolution))
                .order_by(Episode.season, Episode.number, Release.seeders.desc()))
    else:
        return (Release.select(Release)
                .join(Episode)
                .where((Episode.series == series_id) & (Release.resolution <= max_resolution))
                .order_by(Episode.season, Episode.number, Release.seeders.desc()))


def get_tags_for_series(series):
    return (Tag
            .select()
            .join(SeriesTag)
            .join(Series)
            .where(Series.id == series.id))

# def get_releases_for_episode(episode):
#   return (Release.select()
#       .join(Episode)
#       .where((Episode.id == episode.id))
#       .order_by(Release.seeders))


def connect(app_dir, should_setup=False):
    logging.debug(f"Using SQLite version {sqlite3.sqlite_version}")
    logging.debug(f"Full text search 5? {FTS5Model.fts5_installed()}")

    database = os.path.join(app_dir, DATABASE_FILENAME)
    logging.debug(f"Using local database at {database}")
    db.init(database)
    db.connect()
    if should_setup:
        setup()


def close():
    db.close()


###########
# LOCAL DB SETUP
###########

TAGS = {
    "action": "Action", "adventure": "Adventure", "animation": "Animation", "anime": "Anime", "awards-show": "Awards Show", "children": "Children", "comedy": "Comedy", "crime": "Crime", "documentary": "Documentary", "drama": "Drama", "family": "Family", "fantasy": "Fantasy", "food": "Food", "game-show": "Game Show", "history": "History", "home-and-garden": "Home and Garden", "horror": "Horror", "indie": "Indie", "martial-arts": "Martial Arts", "mini-series": "Mini-Series", "musical": "Musical", "mystery": "Mystery", "news": "News", "podcast": "Podcast", "reality": "Reality", "romance": "Romance", "science-fiction": "Science Fiction", "soap": "Soap", "special-interest": "Special Interest", "sport": "Sport", "suspense": "Suspense", "talk Show": "Talk Show", "thriller": "Thriller", "travel": "Travel", "western": "Western", "war": "War"
}


def setup():
    db.create_tables([
        Series,
        SeriesIndex,
        Episode,
        EpisodeIndex,
        Release,
        Tag,
        SeriesTag,
        SyncLog,
    ], safe=True)

    if Tag.select().count() == 0:
        for slug, name in TAGS.items():
            Tag.create(slug=slug, name=name)
