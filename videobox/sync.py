from peewee import chunked
import time
from datetime import datetime, timezone
from requests.exceptions import HTTPError, ReadTimeout
from urllib3.exceptions import ReadTimeoutError
import logging
import videobox.api as api
import videobox.model as model
from videobox.model import SeriesTag, db, Series, SeriesIndex, Episode, EpisodeIndex, Release, SyncLog

INSERT_CHUNK_SIZE = 90      # SQLite has a limit of total 999 max variables
REQUEST_CHUNK_SIZE = 450    # Total URI must be < 4096


class SyncWorker(object):

    def __init__(self, client_id, progress_callback=None, done_callback=None):
        self.client_id = client_id
        self.progress_callback = progress_callback
        self.done_callback = done_callback

    def run(self):
        last_log = model.get_last_log()
        start = time.time()

        # Start log line
        current_log = SyncLog.create(description="Started sync")

        response = []
        if last_log:
            logging.info("Last update done at {0} UTC, requesting updates since then".format(
                last_log.timestamp.isoformat()))
            if self.progress_callback:
                self.progress_callback("Getting updated series...")
            # Ensure UTC tz
            response = self.do_request(lambda: api.get_updated_series(
                self.client_id, last_log.timestamp.replace(tzinfo=timezone.utc)), retries=3)
        else:
            logging.info("No local database found, starting import")
            if self.progress_callback:
                self.progress_callback("First run: import running series...")

            response = self.do_request(
                lambda: api.get_running_series(self.client_id), retries=3)

        if not response:
            # @@TODO pass any error to current_log
            self.update_log(current_log, status="E",
                            description="Unable to contact sync server")
            return

        # Save alert from server, if any
        alert = response["alert"]

        # Grab series
        series_ids = response['series']
        if series_ids:
            logging.debug(
                "Got {0} series, starting update".format(len(series_ids)))
            series_count = self.sync_series(series_ids)

        # Grab episodes
        episode_ids = response['episodes']
        if episode_ids:
            logging.debug(
                "Got {0} episodes, starting update".format(len(episode_ids)))
            episode_count = self.sync_episodes(episode_ids)

        # Grab releases
        release_ids = response['releases']
        if release_ids:
            release_count = self.sync_releases(release_ids)

        elapsed_time = time.time()-start
        if any([series_ids, episode_ids, release_ids]):
            description = "Finished in {:.2f}s: updated {} series, {} episodes, and {} releases".format(
                elapsed_time, series_count, episode_count, release_count
            )
        else:
            description = "Finished in {:.2f}s: no updates were found".format(
                elapsed_time)

        # Mark sync successful
        self.update_log(current_log, status="K", description=description)

        logging.info(f"{description}")

        if self.done_callback:
            self.done_callback(description, alert)

    def sync_series(self, remote_ids):
        instant = datetime.utcnow()

        local_ids = [s.id for s in Series.select(Series.id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Always request all remote ids so we have a change to update existing series
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} series...", 25 + percent)

            logging.debug(
                f"Found missing {new_ids_count} of {len(remote_ids)} series")
            # Reuqest old and new series
            response = self.do_chunked_request(
                api.get_series_with_ids, remote_ids, callback)
            if response:
                with db.atomic():
                    logging.debug("Saving series to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        # Insert new series and attempt to update existing ones
                        (Series.insert_many(batch)
                         .on_conflict(
                            conflict_target=[Series.id],
                            # Pass down values from insert clause
                            preserve=[Series.name, Series.overview, Series.network, Series.poster_url, Series.fanart_url],
                            update={Series.last_updated_on: instant})
                         .execute())
                        for series in batch:
                            (SeriesIndex.insert({
                                SeriesIndex.rowid: series['id'],
                                SeriesIndex.name: series['name']
                            })
                                # Just replace name edits
                                .on_conflict_replace()
                                .execute())
                SeriesIndex.optimize()

            #  Series tags
            response = self.do_chunked_request(
                api.get_series_tags_for_ids, remote_ids, callback)
            if response:
                with db.atomic():
                    logging.debug("Saving series tags to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        (SeriesTag.insert_many(batch)
                            .on_conflict(action="nothing", conflict_target=[SeriesTag.series, SeriesTag.tag])
                         .execute())

        return len(remote_ids)

    def sync_episodes(self, remote_ids):
        instant = datetime.utcnow()

        local_ids = [e.id for e in Episode.select(Episode.id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Always request all remote ids so we have a change to update existing episodes
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} episodes...", 50 + percent)

            logging.debug(
                f"Found missing {new_ids_count} of {len(remote_ids)} episodes")
            # Request old and new episodes
            response = self.do_chunked_request(
                api.get_episodes_with_ids, remote_ids, callback)
            if response:
                with db.atomic():
                    logging.debug("Saving episodes to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        # We need to cope with the unique constraint for (series, season, number)
                        #   index because we cannot rely on episodes id's,
                        #   they are often changed when TVDB users update them
                        (Episode
                            .insert_many(batch)
                            .on_conflict(
                                conflict_target=[
                                    Episode.series, Episode.season, Episode.number],
                                # Pass down values from insert clause 
                                preserve=[Episode.name, Episode.overview, Episode.aired_on, Episode.thumbnail_url],
                                update={Episode.last_updated_on: instant})
                            .execute())
                        # EpisodeIndex.insert({
                        #     EpisodeIndex.rowid: episode_id,
                        #     EpisodeIndex.name: episode.name,
                        #     EpisodeIndex.overview: episode.overview}).execute()

        return len(remote_ids)

    def sync_releases(self, remote_ids):

        local_ids = [r.id for r in Release.select(Release.id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Always request all remote ids so we have a chance to update existing releases
        if remote_ids:
            def callback(percent, remaining):
                self.progress_callback(
                    f"Updating {remaining} releases...", 75 + percent)

            logging.debug(
                f"Found missing {new_ids_count} of {len(remote_ids)} releases")
            # Request old and new releases
            response = self.do_chunked_request(
                api.get_releases_with_ids, remote_ids, callback)
            if response:
                with db.atomic():
                    logging.debug("Saving releases to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        (Release
                            .insert_many(batch)
                            .on_conflict(
                                conflict_target=[Release.id],
                                # Pass down values from insert clause
                                preserve=[Release.peers, Release.seeders, Release.last_updated_on])
                            .execute())

        return len(remote_ids)

    def progress(self, value, min, max):
        return self.scale_between(value, 0, 25, min, max)

    def scale_between(self, value, min_allowed, max_allowed, min, max):
        return (max_allowed - min_allowed) * (value - min) / (max - min) + min_allowed

    def update_log(self, log, status, description=""):
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
            logging.debug(
                f"Requesting {index + 1} of {ids_count // REQUEST_CHUNK_SIZE + 1} chunks")
            result.extend(self.do_request(
                lambda: handler(self.client_id, chunked_ids)))
        return result

    def do_request(self, handler, retries=1):
        for index in reversed(range(retries)):
            try:
                response = handler()
                response.raise_for_status()  # Raise an exeption on HTTP errors
            except Exception as ex:
                self.log_network_error(ex, index)
                time.sleep(2)
                continue  # Next retry
            return response.json()
        return []

    def log_network_error(self, ex, retry):
        if isinstance(ex, TimeoutError) or isinstance(ex, ReadTimeoutError) or isinstance(ex, ReadTimeout):
            logging.warn(
                f'Server timed out while handling the request {ex}, {"retrying" if retry else "skipped"}')
        elif isinstance(ex, HTTPError):
            logging.error(
                f'A server error occured while handling the request {ex}, {"retrying" if retry else "skipped"}')
        else:
            # Cannot handle this
            raise ex
