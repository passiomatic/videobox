import time
from datetime import datetime, timedelta, timezone
from threading import Thread, Event
from peewee import chunked, fn
from requests.exceptions import HTTPError, ReadTimeout
from flask import current_app
import videobox.api as api
import videobox.models as models
import videobox.scraper as scraper
from videobox.models import SyncLog

REQUEST_CHUNK_SIZE = 450        # Total URI must be < 4096
TIMEOUT_BEFORE_RETRY = 5        # Seconds
SYNC_INTERVAL = 60*60*2         # Seconds
MIN_SYNC_INTERVAL = 60*15       # Seconds

# The only sync worker
sync_worker = None


class SyncError(Exception):
    pass

def default_progress_callback(message):
    pass

def default_done_callback(message, alert):
    pass

class SyncWorker(Thread):

    def __init__(self, client_id, progress_callback=default_progress_callback, done_callback=default_done_callback):
        super().__init__(name="Sync worker")
        self.app = current_app._get_current_object()
        self.client_id = client_id
        self.progress_callback = progress_callback
        self.done_callback = done_callback
        # Start sync immediately at startup
        self.interval = 0
        self.abort_event = Event()        

    def abort(self):
        self.abort_event.set()

    def run(self):
        # Set up a recurring execution unless asked to abort
        while not self.abort_event.is_set():
            if self.interval:
                self.app.logger.debug(f"Waiting for {self.interval}s before next sync...")
            self.abort_event.wait(self.interval)
            if self.abort_event.is_set():
                self.app.logger.debug(f"Stopped {self.name} #{id(self)} thread")
                return             
            self._run_sync()            
            # Schedule next sync
            self.interval = SYNC_INTERVAL

    def _run_sync(self):
        last_log = models.get_last_successful_log()
        start_time = time.time()

        # Manually push the app context to make Flask
        #   logger to work on the separate thread
        with self.app.app_context():
            if last_log:
                sync_interval = datetime.now(timezone.utc) - last_log.timestamp.replace(tzinfo=timezone.utc) 
                # timedelta.seconds upper bound is 3600*24
                if sync_interval.days == 0 and sync_interval.seconds < MIN_SYNC_INTERVAL:
                    self.app.logger.info(f"Sync request is below min. time interval of {MIN_SYNC_INTERVAL}s, ignored")
                    return

            current_log = SyncLog.create(description="Started sync")

            alert = ""
            try:
                if last_log:
                    alert, tags_count, series_count, episode_count, release_count = self.update_library(
                        last_log)
                else:
                    tags_count, series_count, episode_count, release_count = self.import_library()
            except SyncError as ex:
                self.update_log(current_log, status=models.SYNC_ERROR, description=str(ex))
                self.done_callback(str(ex), alert)
                return

            elapsed_time = time.time()-start_time
            if any([series_count, episode_count, release_count]):
                description = f"added/updated {tags_count} tags, {series_count} series, {episode_count} episodes, and {release_count} torrents"
            else:
                description = "no updates were found"

            # Mark import/sync successful
            self.update_log(current_log, status=models.SYNC_OK, description=description)

            self.app.logger.info(f"Finished in {elapsed_time:.1f}s: {description}")
            print(f"Finished library sync: {description}")

            self.done_callback(description, alert)

            scraper.scrape_releases()

    def import_library(self):
        tags_count, series_count, episode_count, release_count = 0, 0, 0, 0

        self.app.logger.info("No local database found, starting full import")

        self.progress_callback("Importing all tags...")

        json = self.do_json_request(
            lambda: api.get_all_tags(self.client_id), retries=3)
        if json:
            self.progress_callback("Saving tags to library...")
            tags_count = models.save_tags(self.app, json)

        self.progress_callback("Importing all series...")

        json = self.do_json_request(
            lambda: api.get_all_series(self.client_id))
        if json:
            self.progress_callback("Saving series to library...")
            series_count = models.save_series(self.app, json)

        self.progress_callback("Importing all series tags...")

        json = self.do_json_request(
            lambda: api.get_all_series_tags(self.client_id))
        if json:
            models.save_series_tags(self.app, json)

        self.progress_callback("Importing all episodes...")

        json = self.do_json_request(
            lambda: api.get_all_episodes(self.client_id))
        if json:
            self.progress_callback("Saving episodes to library...")
            episode_count = models.save_episodes(self.app, json, 
                                                 callback=lambda percent: self.progress_callback(f"Saving episodes to library {percent}%"))

        self.progress_callback("Importing all torrents...")

        json = self.do_json_request(
            lambda: api.get_all_releases(self.client_id))
        if json:
            release_count = models.save_releases(self.app, json, 
                                                 callback=lambda percent: self.progress_callback(f"Saving torrents to library {percent}%"))

        return tags_count, series_count, episode_count, release_count

    def update_library(self, last_log):
        tags_count, series_count, episode_count, release_count = 0, 0, 0, 0

        self.app.logger.info("Last update done at {0} UTC, requesting updates since then".format(
            last_log.timestamp.isoformat()))
        self.progress_callback("Getting updated series...")
        # Ensure UTC timezone
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

        return alert, tags_count, series_count, episode_count, release_count

    def sync_tags(self, remote_ids):
        count = 0

        # Always request all remote ids so we have a chance to update existing series
        if remote_ids:
            def callback(remaining):
                self.progress_callback(
                    f"Updating {remaining} tags...")

            # Request all remote tags
            response = self.do_chunked_request(
                api.get_tags_with_ids, remote_ids, callback)
            if response:
                count = models.save_tags(self.app, response)

        return count

    def sync_series(self, remote_ids):

        # @@TODO
        # local_count = (Series.select(fn.Count(Series.id))
        #                .where((Series.id << remote_ids))
        #                .scalar())
        # missing_count = len(remote_ids) - local_count
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing series
        if remote_ids:
            def callback(remaining):
                self.progress_callback(
                    f"Updating {remaining} series...")

            # self.app.logger.debug(
            #     f"Found missing {missing_count} of {len(remote_ids)} series")
            # Request old and new series
            response = self.do_chunked_request(
                api.get_series_with_ids, remote_ids, callback)
            if response:
                count = models.save_series(self.app, response)

            #  Series tags
            response = self.do_chunked_request(
                api.get_series_tags_for_ids, remote_ids, callback)
            if response:
                models.save_series_tags(self.app, response)

        return count



    def sync_episodes(self, remote_ids):

        # local_ids = [e.id for e in Episode.select(Episode.id)]
        # new_ids = set(remote_ids) - set(local_ids)
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing episodes
        if remote_ids:
            # self.app.logger.debug(
            #     f"Found missing {missing_count} of {len(remote_ids)} episodes")
            # Request old and new episodes
            response = self.do_chunked_request(
                api.get_episodes_with_ids, remote_ids, callback=lambda remaining: self.progress_callback(f"Updating {remaining} episodes..."))
            if response:
                count = models.save_episodes(self.app, response)

        return count

    def sync_releases(self, remote_ids):

        # local_ids = [r.id for r in Release.select(Release.id)]
        # new_ids = set(remote_ids) - set(local_ids)
        count, missing_count = 0, 0

        # Always request all remote ids so we have a chance to update existing releases
        if remote_ids:
            # self.app.logger.debug(
            #     f"Found missing {missing_count} of {len(remote_ids)} releases")
            # Request old and new releases
            response = self.do_chunked_request(
                api.get_releases_with_ids, remote_ids, 
                callback=lambda remaining: self.progress_callback(f"Updating {remaining} torrents..."))
            if response:
                count = models.save_releases(self.app, response)

        return count

    def update_log(self, log, status, description):
        log.status = status
        log.description = description
        log.save()

    def do_chunked_request(self, handler, ids, callback=None):
        result = []
        ids_count = len(ids)
        for index, chunked_ids in enumerate(chunked(ids, REQUEST_CHUNK_SIZE)):
            if callback:
                callback(ids_count - index*REQUEST_CHUNK_SIZE)
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
            "Server timed out while handling the request")