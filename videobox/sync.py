from peewee import chunked, fn
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
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


class SyncError(Exception):
    pass


class SyncWorker(Thread):

    def __init__(self, client_id, progress_callback=None, done_callback=None):
        super().__init__(name="Sync worker")
        self.app = current_app._get_current_object()
        self.client_id = client_id
        self.progress_callback = progress_callback
        self.done_callback = done_callback

    def run(self):
        last_log = models.get_last_log()
        start_time = time.time()

        # Manually push the app context to make Flask
        #   logger to work on the separate thread
        with self.app.app_context():
            current_log = SyncLog.create(description="Started import/sync")

            alert = ""
            try:
                if last_log:
                    alert, series_count, episode_count, release_count = self.update_library(
                        last_log)
                else:
                    series_count, episode_count, release_count = self.import_library()
            except SyncError as ex:
                self.update_log(current_log, status=models.SYNC_ERROR, description=str(ex))
                if self.done_callback:
                    self.done_callback(str(ex), alert)
                return

            elapsed_time = time.time()-start_time
            if any([series_count, episode_count, release_count]):
                description = f"Added/updated {series_count} series, {episode_count} episodes, and {release_count} torrents"
            else:
                description = "No updates were found"

            # Mark import/sync successful
            self.update_log(current_log, status=models.SYNC_OK, description=description)

            self.app.logger.info(f"Finished in {elapsed_time:.1f}s: {description}")

            if self.done_callback:
                self.done_callback(description, alert)

    def import_library(self):
        series_count, episode_count, release_count = 0, 0, 0
        instant = datetime.utcnow()

        self.app.logger.info("No local database found, starting full import")
        
        if self.progress_callback:
            self.progress_callback("Importing all tags...", 0)

        json = self.do_json_request(
            lambda: api.get_all_tags(self.client_id), retries=3)
        if json:
            if self.progress_callback:
                self.progress_callback("Saving tags to library...", 12.5)
            self.save_tags(json)

        if self.progress_callback:
            self.progress_callback("Importing all series...", 25)

        json = self.do_json_request(
            lambda: api.get_all_series(self.client_id))
        if json:
            if self.progress_callback:
                self.progress_callback("Saving series to library...", 37.5)
            series_count = self.save_series(json, instant)

        if self.progress_callback:
            self.progress_callback("Importing all series tags...", 50)

        json = self.do_json_request(
            lambda: api.get_all_series_tags(self.client_id))
        if json:
            self.save_series_tags(json)

        if self.progress_callback:
            self.progress_callback("Importing all episodes...", 62.5)

        json = self.do_json_request(
            lambda: api.get_all_episodes(self.client_id))
        if json:
            if self.progress_callback:
                self.progress_callback("Saving episodes to library...", 75)
            episode_count = self.save_episodes(json, instant)

        if self.progress_callback:
            self.progress_callback("Importing all torrents...", 87.5)

        json = self.do_json_request(
            lambda: api.get_all_releases(self.client_id))
        if json:
            if self.progress_callback:
                self.progress_callback("Saving torrents to library...", 87.5)            
            release_count = self.save_releases(json, instant)

        return series_count, episode_count, release_count

    def update_library(self, last_log):
        series_count, episode_count, release_count = 0, 0, 0

        self.app.logger.info("Last update done at {0} UTC, requesting updates since then".format(
            last_log.timestamp.isoformat()))
        if self.progress_callback:
            self.progress_callback("Getting updated series...")
        # Ensure UTC tz
        json = self.do_json_request(lambda: api.get_updated_series(
            self.client_id, last_log.timestamp.replace(tzinfo=timezone.utc)), retries=3)

        # Save alert from server, if any
        alert = json["alert"]

        tag_ids = json['tags']
        if tag_ids:
            self.app.logger.debug(
                "Got {0} tags, starting update".format(len(tag_ids)))
            tags_count = self.sync_tags(tag_ids)        

        # Grab series
        series_ids = json['series']
        if series_ids:
            self.app.logger.debug(
                "Got {0} series, starting update".format(len(series_ids)))
            series_count = self.sync_series(series_ids)

        # Grab episodes
        episode_ids = json['episodes']
        if episode_ids:
            self.app.logger.debug(
                "Got {0} episodes, starting update".format(len(episode_ids)))
            episode_count = self.sync_episodes(episode_ids)

        # Grab releases
        release_ids = json['releases']
        if release_ids:
            self.app.logger.debug(
                "Got {0} releases, starting update".format(len(release_ids)))
            release_count = self.sync_releases(release_ids)

        return alert, series_count, episode_count, release_count

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

    def sync_tags(self, remote_ids):
        count = 0

        # Always request all remote ids so we have a chance to update existing series
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} tags...", 25 + percent)

            # Request all remote tags
            response = self.do_chunked_request(
                api.get_tags_with_ids, remote_ids, callback)
            if response:
                count = self.save_tags(response)

        return count
    
    def sync_series(self, remote_ids):
        instant = datetime.utcnow()

        # @@TODO
        # local_count = (Series.select(fn.Count(Series.id))
        #                .where((Series.id << remote_ids))
        #                .scalar())
        # missing_count = len(remote_ids) - local_count
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing series
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} series...", 25 + percent)

            self.app.logger.debug(
                f"Found missing {missing_count} of {len(remote_ids)} series")
            # Request old and new series
            response = self.do_chunked_request(
                api.get_series_with_ids, remote_ids, callback)
            if response:
                count = self.save_series(response, instant)

            #  Series tags
            response = self.do_chunked_request(
                api.get_series_tags_for_ids, remote_ids, callback)
            if response:
                self.save_series_tags(response)

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

    def save_series_tags(self, response):
        self.app.logger.debug("Saving series tags to database...")
        for batch in chunked(response, INSERT_CHUNK_SIZE):
            (SeriesTag.insert_many(batch)
                # Ignore duplicate rows
                .on_conflict_ignore()
                .execute())

    def sync_episodes(self, remote_ids):
        instant = datetime.utcnow()

        # local_ids = [e.id for e in Episode.select(Episode.id)]
        # new_ids = set(remote_ids) - set(local_ids)
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing episodes
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} episodes...", 50 + percent)

            self.app.logger.debug(
                f"Found missing {missing_count} of {len(remote_ids)} episodes")
            # Request old and new episodes
            response = self.do_chunked_request(
                api.get_episodes_with_ids, remote_ids, callback)
            if response:
                count = self.save_episodes(response, instant)

        return count

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

    def sync_releases(self, remote_ids):
        instant = datetime.utcnow()

        # local_ids = [r.id for r in Release.select(Release.id)]
        # new_ids = set(remote_ids) - set(local_ids)
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing releases
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} torrents...", 75 + percent)

            self.app.logger.debug(
                f"Found missing {missing_count} of {len(remote_ids)} releases")
            # Request old and new releases
            response = self.do_chunked_request(
                api.get_releases_with_ids, remote_ids, callback)
            if response:
                count = self.save_releases(response, instant)

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

    def progress(self, value, min, max):
        return self.scale_between(value, 0, 25, min, max)

    def scale_between(self, value, min_allowed, max_allowed, min, max):
        return (max_allowed - min_allowed) * (value - min) / (max - min) + min_allowed

    def update_log(self, log, status, description):
        log.status = status
        log.description = description
        log.save()

    def do_chunked_request(self, handler, ids, callback=None):
        result = []
        ids_count = len(ids)
        for index, chunked_ids in enumerate(chunked(ids, REQUEST_CHUNK_SIZE)):
            if callback:
                percent = self.progress(index*REQUEST_CHUNK_SIZE, 0, ids_count)
                callback(percent, ids_count -
                         index*REQUEST_CHUNK_SIZE)
            self.app.logger.debug(
                f"Requesting {index + 1} of {ids_count // REQUEST_CHUNK_SIZE + 1} chunks")
            json = self.do_json_request(
                lambda: handler(self.client_id, chunked_ids))
            result.extend(json)
        return result

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
            return response.json()
        # No more retries, giving up
        raise SyncError(
            "Server timed out while handling the request. Please try again later.")
