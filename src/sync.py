import api
from peewee import chunked, IntegrityError
from model import SeriesTag, db, Series, Episode, EpisodeIndex, Release, SyncLog
from datetime import datetime
import time
import utilities
from kivy.logger import Logger
from threading import Thread
from kivy.clock import Clock
from functools import partial
from requests.exceptions import HTTPError, ReadTimeout
from urllib3.exceptions import ReadTimeoutError

INSERT_CHUNK_SIZE = 90      # Sqlite has a limit of total 999 max variables
REQUEST_CHUNK_SIZE = 450    # Total URI must be < 4096


class SyncWorker(Thread):

    def __init__(self, client_id, progress_callback=None, done_callback=None):
        super().__init__(name="Sync worker")
        self.client_id = client_id
        self.progress_callback = progress_callback
        self.done_callback = done_callback
        
    def get_last_log(self):
        return SyncLog.select().where(SyncLog.status == "K").order_by(SyncLog.timestamp.desc()).get_or_none()

    def update_log(self, log, status, description=""):
        log.status = status
        log.description = description
        log.save()

    def run(self):
        last_log = self.get_last_log()
        start = time.time()

        # Start log line
        current_log = SyncLog.create()

        if last_log:
            Logger.info("App: Last sync done at {0} UTC, requesting updates since then".format(
                last_log.timestamp.isoformat()))
            if self.progress_callback:
                Clock.schedule_once(
                    partial(self.progress_callback, "Getting updated series..."))

            response = self.do_request(lambda: api.get_updated_series(
                self.client_id, last_log.timestamp), retries=3)
        else:
            Logger.info("App: No previous sync found, starting import")
            if self.progress_callback:
                Clock.schedule_once(
                    partial(self.progress_callback, "First run: import running series..."))

            response = self.do_request(
                lambda: api.get_running_series(self.client_id), retries=3)

        if not response:
            # @@TODO pass any error to current_log
            self.update_log(current_log, "E",  "Unable to contact server")
            return

        # Grab series
        series_ids = response['series']
        if series_ids:
            Logger.debug(
                "App: Got {0} series, starting sync".format(len(series_ids)))
            series_count = self.sync_series(series_ids)

        # Grab episodes
        episode_ids = response['episodes']
        if episode_ids:
            Logger.debug(
                "App: Got {0} episodes, starting sync".format(len(episode_ids)))
            episode_count = self.sync_episodes(episode_ids)

        # Grab releases
        release_ids = response['releases']
        if release_ids:
            release_count = self.sync_releases(release_ids)

        elapsed_time = time.time()-start
        if any([series_ids, episode_ids, release_ids]):
            description = "Finished sync in {:.2f}s: updated {} series, {} episodes, and {} releases".format(
                elapsed_time, series_count, episode_count, release_count
            )
        else:
            description = "Finished sync in {:.2f}s, no updates found".format(elapsed_time)

        # Mark sync successful
        self.update_log(current_log, "K", description)

        Logger.info(f"App: {description}")

        if self.done_callback:
            Clock.schedule_once(
                partial(self.done_callback, description))

    def sync_series(self, remote_ids):
        instant = datetime.utcnow()

        local_ids = [s.tvdb_id for s in Series.select(Series.tvdb_id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Always request all remote ids so we have a change to update existing series
        if remote_ids:
            def progress_callback(percent, remaining):
                if self.progress_callback:
                    pass
                    # wx.CallAfter(self.progress_callback,
                    #              f"Syncing {remaining} series...", 25 + percent)

            Logger.debug(
                f"App: Found missing {new_ids_count} of {len(remote_ids)} series")
            # Reuqest old and new series
            response = self.do_chunked_request(
                api.get_series_with_ids, remote_ids, progress_callback)
            if response:
                with db.atomic():
                    Logger.debug("App: Saving series to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        # Insert new series and attempt to update existing ones
                        (Series.insert_many(batch)
                         .on_conflict(
                            conflict_target=[Series.tvdb_id],
                            update={Series.last_updated_on: instant})
                         .execute())
            
            #  Series tags
            # response = self.do_chunked_request(
            #     api.get_series_tags_for_ids, remote_ids, progress_callback)
            # if response:
            #     with db.atomic():
            #         Logger.debug("App: Saving series tags to database...")
            #         for batch in chunked(response, INSERT_CHUNK_SIZE):
            #             (SeriesTag.insert_many(batch)
            #              .execute())                        

        return new_ids_count

    def sync_episodes(self, remote_ids):
        instant = datetime.utcnow()

        local_ids = [e.tvdb_id for e in Episode.select(Episode.tvdb_id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Always request all remote ids so we have a change to update existing episodes
        if remote_ids:
            def progress_callback(percent, remaining):
                if self.progress_callback:
                    pass
                    # wx.CallAfter(self.progress_callback,
                    #              f"Syncing {remaining} episodes...", 50 + percent)

            Logger.debug(
                f"App: Found missing {new_ids_count} of {len(remote_ids)} episodes")
            # Request old and new episodes
            response = self.do_chunked_request(
                api.get_episodes_with_ids, remote_ids, progress_callback)
            if response:
                with db.atomic():
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        # We need to cope with the unique constraint for (series, season, number)
                        #   index because we cannot rely on episodes id's,
                        #   they are changed when TVDB users update them
                        (Episode
                            .insert_many(batch)
                            .on_conflict(
                                conflict_target=[
                                    Episode.series, Episode.season, Episode.number],
                                update={Episode.last_updated_on: instant})
                            .execute())
                        # EpisodeIndex.insert({
                        #     EpisodeIndex.rowid: episode_id,
                        #     EpisodeIndex.name: episode.name,
                        #     EpisodeIndex.overview: episode.overview}).execute()

        return new_ids_count

    def sync_releases(self, remote_ids):

        local_ids = [r.id for r in Release.select(Release.id)]
        new_ids = list(set(remote_ids) - set(local_ids))
        new_ids_count = len(new_ids)

        # Request new releases only, we cannot "update" releases
        if new_ids:
            def progress_callback(percent, remaining):
                if self.progress_callback:
                    pass
                    # wx.CallAfter(self.progress_callback,
                    #              f"Syncing {remaining} releases...", 75 + percent)

            Logger.debug(
                f"App: Found missing {new_ids_count} of {len(remote_ids)} releases")
            # Request new releases only
            response = self.do_chunked_request(
                api.get_releases_with_ids, new_ids, progress_callback)
            if response:
                with db.atomic():
                    Logger.debug("App: Saving releases to database...")
                    for batch in chunked(response, INSERT_CHUNK_SIZE):
                        Release.insert_many(batch).execute()

        return new_ids_count

    def do_chunked_request(self, handler, ids, progress_callback=None):
        result = []
        ids_count = len(ids)
        for index, chunked_ids in enumerate(chunked(ids, REQUEST_CHUNK_SIZE)):
            if progress_callback:
                percent = self.progress(index*REQUEST_CHUNK_SIZE, 0, ids_count)
                progress_callback(percent, ids_count -
                                  index*REQUEST_CHUNK_SIZE)
            Logger.debug(
                f"App: Requesting {index + 1} of {ids_count // REQUEST_CHUNK_SIZE + 1} chunks")
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
                continue # Next retry
            return response.json()
        return []

    def log_network_error(self, ex, retry):
        if isinstance(ex, TimeoutError) or isinstance(ex, ReadTimeoutError) or isinstance(ex, ReadTimeout):
            Logger.error(f'App: Server timed out while handling the request {ex}, {"retrying" if retry else "skipped"}')
        elif isinstance(ex, HTTPError):
            Logger.error(f'App: A server error occured while handling the request {ex}, {"retrying" if retry else "skipped"}')
        else:
            # Cannot handle this
            raise ex

    def progress(self, value, min, max):
        return utilities.scale_between(value, 0, 25, min, max)
