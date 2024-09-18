from datetime import datetime, timedelta, timezone
from peewee import *
from playhouse.migrate import migrate, SqliteMigrator
from playhouse.reflection import Introspector
from playhouse.sqlite_ext import FTS5Model, SearchField, RowIDField
from playhouse.flask_utils import FlaskDB
from . import iso639

# @@TODO check 
# SQLite >3.32.0 has a limit of total 32766 max variables (SQLITE_MAX_VARIABLE_NUMBER)
# https://stackoverflow.com/a/64419474 
# https://stackoverflow.com/q/35616602
INSERT_CHUNK_SIZE = 999 // 15   # Series class has the max numbes of fields 

SYNC_STARTED = "S"
SYNC_ERROR = "E"
SYNC_OK = "K"

TAG_GENRE = "G"
TAG_KEYWORD = "K"

TRACKER_NOT_CONTACTED = 'N'
TRACKER_PROTOCOL_ERROR = 'P'
TRACKER_DNS_ERROR = 'D'
TRACKER_OK = 'K'
TRACKER_TIMED_OUT = 'T'

TRACKERS_ALIVE = [TRACKER_NOT_CONTACTED, TRACKER_OK, TRACKER_TIMED_OUT]

class AppDB(FlaskDB):
    '''
    Specialised FlaskDB which deals with testing memory 
      sqlite database, see: https://t.ly/susgy
    '''
    def _register_handlers(self, app):
        if app.config['TESTING']:
            return
        app.before_request(self.connect_db)
        app.teardown_request(self.close_db)
        
# Defer init in app creation
db_wrapper = AppDB()

class SyncLog(db_wrapper.Model):
    timestamp = TimestampField(utc=True)
    status = FixedCharField(max_length=1, default=SYNC_STARTED)
    description = TextField(default="")

    def __str__(self):
        return f"[{self.status} {self.timestamp}] {self.description}"


def get_last_log():
    return SyncLog.select().where(SyncLog.status != SYNC_STARTED).order_by(SyncLog.timestamp.desc()).get_or_none()


def get_last_successful_log():
    return SyncLog.select().where(SyncLog.status == SYNC_OK).order_by(SyncLog.timestamp.desc()).get_or_none()


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
    language = FixedCharField(max_length=2)
    followed_since = DateField(null=True)


    @property
    def poster(self):
        return self.poster_url or "/static/default-poster.png"
    

    @property
    def imdb_url(self):
        if self.imdb_id:
            return f"https://www.imdb.com/title/{self.imdb_id}/"
        else:
            return ""
        
    @property
    def tmdb_url(self):
        return f"https://www.themoviedb.org/tv/{self.tmdb_id}"

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
    thumbnail_url = CharField(default="")

    @property
    def season_episode_id(self):
        return "S{:02}.E{:02}".format(self.season, self.number)
    
    @property
    def thumbnail(self):
        return self.thumbnail_url or "/static/default-still.png"
    
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

    # @property
    # def next_scrape_on(self):
    #     import videobox.scraper as scraper
    #     age = datetime.now(timezone.utc) - self.added_on.replace(tzinfo=timezone.utc)
    #     return scraper.get_scrape_threshold(age.days)

    @property
    def languages(self):
        return iso639.extract_languages(self.name)


class Tracker(db_wrapper.Model):
    url = CharField(unique=True)    
    status = FixedCharField(max_length=1, default=TRACKER_NOT_CONTACTED)
    last_scraped_on = DateTimeField(null=True)


def save_trackers(app, trackers):
    """
    Insert new trackers and ignore existing ones
    """    
    count = 0
    app.logger.debug("Saving trackers to database...")
    for batch in chunked(trackers, INSERT_CHUNK_SIZE):
        # Skip rows causing the conflict, see:
        #   https://sqlite.org/lang_conflict.html
        count += (Tracker.insert_many(batch)
                  .on_conflict_ignore()
                  .as_rowcount()
                  .execute())                
    return count

def save_tags(app, tags):
    """
    Insert new tags and attempt to update existing ones
    """
    count = 0
    app.logger.debug("Saving tags to database...")
    for batch in chunked(tags, INSERT_CHUNK_SIZE):
        count += (Tag.insert_many(batch)
                  # Replace current tag with new data
                  .on_conflict_replace()
                  .as_rowcount()
                  .execute())
    return count

def save_series(app, series):
    """
    Insert new series and attempt to update existing ones
    """
    count = 0
    app.logger.debug("Saving series to database...")
    for batch in chunked(series, INSERT_CHUNK_SIZE):
        count += (Series.insert_many(batch)
                  .on_conflict(
            conflict_target=[Series.id],
            # Pass down values from insert clause
            preserve=[Series.imdb_id, Series.name, Series.sort_name, Series.language, Series.tagline, Series.overview, Series.network,
                      Series.vote_average, Series.popularity, Series.poster_url, Series.fanart_url, Series.status])
                  .as_rowcount()
                  .execute())
        for series in batch:
            content = ' '.join([series['network'], series['overview']]) 
            # FTS5 insert_many cannot handle upserts
            (SeriesIndex.insert({
                SeriesIndex.rowid: series['id'],                    
                SeriesIndex.name: series['name'],
                SeriesIndex.content: content,
            })
                # Just replace name and content edits
                .on_conflict_replace()
                .execute())
    SeriesIndex.optimize()
    return count

def save_series_tags(app, series_tags):
    count = 0
    app.logger.debug("Saving series tags to database...")
    for batch in chunked(series_tags, INSERT_CHUNK_SIZE):
        count += (SeriesTag.insert_many(batch)
                  # Skip rows causing the conflict, see:
                  #   https://sqlite.org/lang_conflict.html
                  .on_conflict_ignore()
                  .execute())

    return count

def save_episodes(app, episodes, callback=None):
    """
    Insert new episodes and attempt to update existing ones
    """
    count = 0
    app.logger.debug("Saving episodes to database...")
    episode_count = len(episodes)
    for index, batch in enumerate(chunked(episodes, INSERT_CHUNK_SIZE)):
        # We need to cope with the unique constraint for (series, season, number)
        #   index because we cannot rely on episodes id's,
        #   they are often changed when TVDB users update them
        if callback:
            callback(int((index * INSERT_CHUNK_SIZE) / episode_count * 100))        
        count += (Episode
                  .insert_many(batch)
                  .on_conflict(
                      conflict_target=[
                          Episode.series, Episode.season, Episode.number],
                      # Pass down values from insert clause
                      preserve=[Episode.name, Episode.overview,
                                Episode.aired_on, Episode.thumbnail_url])
                  .as_rowcount()
                  .execute())
        # EpisodeIndex.insert({
        #     EpisodeIndex.rowid: episode_id,
        #     EpisodeIndex.name: episode.name,
        #     EpisodeIndex.overview: episode.overview}).execute()
    #EpisodeIndex.optimize()            
    return count

def save_releases(app, releases, callback=None):
    """
    Insert new releases and attempt to update existing ones
    """
    count = 0
    app.logger.debug("Saving releases to database...")
    release_count = len(releases)
    for index, batch in enumerate(chunked(releases, INSERT_CHUNK_SIZE)):
        if callback:
            callback(int((index * INSERT_CHUNK_SIZE) / release_count * 100))
        count += (Release
                  .insert_many(batch)
                  .on_conflict(
                      conflict_target=[Release.id],
                      # Pass down values from insert clause
                      preserve=[Release.leechers, Release.seeders, Release.completed, Release.last_updated_on])
                  .as_rowcount()
                  .execute())
    return count

###########
# DB SETUP
###########

def setup():
    db_wrapper.database.create_tables([
        Series,
        SeriesIndex,
        Episode,
        Release,
        Tracker,
        Tag,
        SeriesTag,
        SyncLog,
    ], safe=True)

    # Run schema update for every fields added after version 0.5

    migrator = SqliteMigrator(db_wrapper.database)
    introspector = Introspector.from_database(db_wrapper.database)
    models = introspector.generate_models()
    Series_ = models['series']
    Episode_ = models['episode']

    column_migrations = []
    
    # Add new columns

    if not hasattr(Series_, 'followed_since'):
        followed_since = DateField(null=True)
        column_migrations.append(migrator.add_column('series', 'followed_since', followed_since))

    # Remove obsolete columns

    if hasattr(Series_, 'last_updated_on'):
        column_migrations.append(migrator.drop_column('series', 'last_updated_on'))

    if hasattr(Episode_, 'last_updated_on'):
        column_migrations.append(migrator.drop_column('episode', 'last_updated_on'))

    # Run all migrations
    with db_wrapper.database.atomic():
        migrate(*column_migrations)

    return len(column_migrations)