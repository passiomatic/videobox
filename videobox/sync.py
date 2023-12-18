from peewee import chunked, fn
import time
from datetime import datetime, timedelta, timezone
from threading import Thread, Event
from requests.exceptions import HTTPError, ReadTimeout
from flask import current_app
import videobox.api as api
import videobox.models as models
from videobox.models import Tag, SeriesTag, Series, SeriesIndex, Episode, Release, SyncLog

# @@TODO check 
# SQLite >3.32.0 has a limit of total 32766 max variables (SQLITE_MAX_VARIABLE_NUMBER)
# https://stackoverflow.com/a/64419474 
# https://stackoverflow.com/q/35616602
INSERT_CHUNK_SIZE = 999 // 15   # Series class has the max numbes of fields 
REQUEST_CHUNK_SIZE = 450        # Total URI must be < 4096
TIMEOUT_BEFORE_RETRY = 5        # Seconds
SYNC_INTERVAL = 60*60*3         # Seconds


# The only sync worker tread
sync_worker = None


class SyncError(Exception):
    pass


class SyncWorker(Thread):

    def __init__(self, client_id, progress_callback=None, done_callback=None):
        super().__init__(name="Sync worker")
        self.app = current_app._get_current_object()
        self.client_id = client_id
        self.progress_callback = progress_callback
        self.done_callback = done_callback
        # Start sync immediately at startup
        self.interval = 0
        self.finished = Event()        

    def cancel(self):
        """Stop the thread's internal timer if it hasn't finished yet"""
        self.finished.set()

    def run(self):
        # Set up a recurring execution
        while not self.finished.is_set():
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                self._run_sync()
                # Schedule next sync
                self.interval = SYNC_INTERVAL

    def _run_sync(self):

        last_log = models.get_last_log()
        start_time = time.time()

        # Manually push the app context to make Flask
        #   logger to work on the separate thread
        with self.app.app_context():

            try:              
                series_count, episode_count, release_count = 0, 0, 0
                current_log = SyncLog.create(description="Started sync")                

                # @@TODO Check freshness
                response = self.do_json_request(
                    lambda: api.get_info(etag=last_log.etag if last_log else ''), retries=3)
                # Modified?                
                if response.status_code == 200:
                    current_log.etag = response.headers['etag'] or ''
                    json = response.json()
                    current_log.expires_on = json['expires_on'] or None
                    current_log.alert = json['alert']
                                                      
                    if last_log:
                        self.app.logger.info("Last sync done at {0} UTC, requesting recent updates".format(last_log.timestamp.isoformat()))                    
                        series_count, episode_count, release_count = self.import_library(quick=True)
                    else:
                        self.app.logger.info("Database is stale, starting full import")    
                        series_count, episode_count, release_count = self.import_library()
                else:
                    # Copy values from last good log line
                    current_log.etag = last_log.etag
                    current_log.expires_on = last_log.expires_on
                    current_log.alert = last_log.alert
                
                elapsed_time = time.time()-start_time
                if any([series_count, episode_count, release_count]):
                    description = f"Added/updated {series_count} series, {episode_count} episodes, and {release_count} torrents"
                else:
                    description = "No updates were found"

                # Mark sync successful
                current_log.status = models.SYNC_OK
                current_log.description = description
                current_log.save()       

                if self.done_callback:
                    self.done_callback(description)

                self.app.logger.info(f"Finished in {elapsed_time:.1f}s: {description}")

            except SyncError as ex:                                
                current_log.status = models.SYNC_ERROR
                current_log.description = str(ex)
                current_log.save()

                if self.done_callback:
                    self.done_callback(str(ex))


    def import_library(self, quick=False):
        series_count, episode_count, release_count = 0, 0, 0
        instant = datetime.utcnow()

        if self.progress_callback:
            self.progress_callback("Importing tags...")

        response = self.do_json_request(
            lambda: api.get_tags(quick), retries=3)
        json = response.json()
        if json:
            if self.progress_callback:
                self.progress_callback("Saving tags to library...")
            self.save_tags(json)

        if self.progress_callback:
            self.progress_callback("Importing series...")

        response = self.do_json_request(
            lambda: api.get_series(quick))
        json = response.json()        
        if json:
            if self.progress_callback:
                self.progress_callback("Saving series to library...")
            series_count = self.save_series(json, instant)

        if self.progress_callback:
            self.progress_callback("Importing series tags...")

        response = self.do_json_request(
            lambda: api.get_series_tags(quick))
        json = response.json()                
        if json:
            self.save_series_tags(json)

        if self.progress_callback:
            self.progress_callback("Importing episodes...")

        response = self.do_json_request(
            lambda: api.get_episodes(quick))
        json = response.json()        
        if json:
            if self.progress_callback:
                self.progress_callback("Saving episodes to library...")
            episode_count = self.save_episodes(json, instant)

        if self.progress_callback:
            self.progress_callback("Importing torrents...")

        response = self.do_json_request(
            lambda: api.get_releases(quick))
        json = response.json()        
        if json:
            if self.progress_callback:
                self.progress_callback("Saving torrents to library...")            
            release_count = self.save_releases(json, instant)

        return series_count, episode_count, release_count

    def save_tags(self, response):
        """
        Insert new tags and attempt to update existing ones
        """
        count = 0
        self.app.logger.debug("Saving tags to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            count += (Tag.insert_many(batch)
                      # Replace current tag with new data
                      .on_conflict_replace()
                      .as_rowcount()
                      .execute())
        return count

    def save_series(self, response, instant):
        """
        Insert new series and attempt to update existing ones
        """
        count = 0
        self.app.logger.debug("Saving series to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            count += (Series.insert_many(batch)
                      .on_conflict(
                conflict_target=[Series.id],
                # Pass down values from insert clause
                preserve=[Series.imdb_id, Series.name, Series.sort_name, Series.tagline, Series.overview, Series.network,
                          Series.vote_average, Series.popularity, Series.poster_url, Series.fanart_url],
                update={Series.last_updated_on: instant})
                .as_rowcount()
                .execute())
            for series in batch:
                content = ' '.join([series['name'], series['network'], series['overview']]) 
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

    def save_series_tags(self, response):
        self.app.logger.debug("Saving series tags to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            (SeriesTag.insert_many(batch)
                # Ignore duplicate rows
                .on_conflict_ignore()
                .execute())

    def save_episodes(self, response, instant):
        """
        Insert new episodes and attempt to update existing ones
        """
        count = 0
        self.app.logger.debug("Saving episodes to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            # We need to cope with the unique constraint for (series, season, number)
            #   index because we cannot rely on episodes id's,
            #   they are often changed when TVDB users update them
            count += (Episode
                      .insert_many(batch)
                      .on_conflict(
                          conflict_target=[
                              Episode.series, Episode.season, Episode.number],
                          # Pass down values from insert clause
                          preserve=[Episode.name, Episode.overview,
                                    Episode.aired_on, Episode.thumbnail_url],
                          update={Episode.last_updated_on: instant})
                      .as_rowcount()
                      .execute())
            # EpisodeIndex.insert({
            #     EpisodeIndex.rowid: episode_id,
            #     EpisodeIndex.name: episode.name,
            #     EpisodeIndex.overview: episode.overview}).execute()
        #EpisodeIndex.optimize()            
        return count

    def save_releases(self, response, instant):
        """
        Insert new releases and attempt to update existing ones
        """
        count = 0
        self.app.logger.debug("Saving releases to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            count += (Release
                      .insert_many(batch)
                      .on_conflict(
                          conflict_target=[Release.id],
                          # Pass down values from insert clause
                          preserve=[Release.leechers, Release.seeders, Release.completed, Release.last_updated_on])
                      .as_rowcount()
                      .execute())
        return count

    def do_json_request(self, handler, retries=1):
        for index in reversed(range(retries)):
            try:
                response = handler()
                response.raise_for_status()  # Raise an exeption on HTTP errors
            except ReadTimeout as ex:
                message = f'Server timed out while handling the request, {"retrying" if index else "skipped"}'
                self.app.logger.warn(message)
                time.sleep(TIMEOUT_BEFORE_RETRY)
                continue  # Next retry
            except HTTPError as ex:
                message = f'Server error {ex.response.status_code} occurred while handling the request, giving up'
                self.app.logger.error(message)
                raise SyncError(message)
            return response
        # No more retries, giving up
        raise SyncError(
            "Server timed out while handling the request. Please try again later.")
