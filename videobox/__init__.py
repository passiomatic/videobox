"""
Videobox package.
"""

__version__ = "0.8.2"
version_info = (0, 8, 2, 0)

import sys
import os
import signal
import logging
from pathlib import Path
import click
import flask 
import sqlite3
import waitress
import uuid
import videobox.models as models
import videobox.filters as filters
from .main import bp as main_blueprint
from videobox.main.announcer import announcer
import videobox.sync as sync
import videobox.scraper as scraper
import tomli_w
try:
    import tomllib as toml  # Python 3.11+
except ImportError:
    import tomli as toml
import videobox.bt as bt



DATABASE_FILENAME = 'library.db'
CONFIG_FILENAME = 'config.toml'
DEFAULT_DATA_DIR = Path.home().joinpath(".videobox")
MAX_WORKER_TIMEOUT = 10 # Seconds

def create_app(app_dir=None, data_dir=None, config_class=None):
    if app_dir:
        app = flask.Flask(__name__, template_folder=os.path.join(app_dir, "templates"), static_folder=os.path.join(app_dir, "static"))
    else:
        app = flask.Flask(__name__)      

    if data_dir:
        data_dir = Path(data_dir)
    else:
        data_dir = DEFAULT_DATA_DIR

    os.makedirs(data_dir, exist_ok=True)

    if config_class:    
        app.config.from_object(config_class)
    else:
        if not app.config['DEBUG']:
            # Replace default Flask logger
            logger = logging.getLogger("app_logger")
            logger.setLevel(logging.INFO)
            file_handler = logging.FileHandler(filename=Path(data_dir).joinpath("videobox.log"), delay=True)
            formatter = logging.Formatter(fmt='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.propagate = False
            app.logger = logger
        app.config['DATABASE_URL'] = f'sqlite:///{data_dir.joinpath(DATABASE_FILENAME)}' 
        config_path = os.path.join(data_dir, CONFIG_FILENAME)
        if app.config.from_file(config_path, load=toml.load, text=False, silent=True):
            app.logger.debug(f"Using configuration file {config_path}")
        else:
            config = get_default_config()
            app.config.from_mapping(config)
            with open(config_path, "wb") as f:
                tomli_w.dump(config, f)

    # Initialize Flask extensions here

    models.db_wrapper.init_app(app)
    models.db_wrapper.database.pragma('foreign_keys', 1, permanent=True)
    models.db_wrapper.database.pragma('journal_mode', 'wal', permanent=True)
    # Create db custom functions
    models.db_wrapper.database.register_function(scraper.get_scrape_threshold, "threshold", num_params=1)

    # Make sure db schema is updated but not while testing
    if not app.config['TESTING']:
        migrate_count = models.setup()
        if migrate_count:
            app.logger.debug(f"Changed {migrate_count} database schema fields")

    app.logger.debug(f"Using SQLite {sqlite3.sqlite_version} with database {app.config['DATABASE_URL']}")
    app.logger.debug(f"Client ID is {app.config['API_CLIENT_ID']}")

    # Register main app routes
    app.register_blueprint(main_blueprint)

    # Register custom template filters
    filters.init_app(app)

    with app.app_context():
        # def on_update_progress(message):
        #     data = flask.render_template(
        #         "_update-progress.html", message=message)            
        #     msg = announcer.format_sse(data=data, event='sync-progress')
        #     announcer.announce(msg)

        def on_update_done(message, alert, last_log=None):
            #     # @@TODO save alert
            #     data = flask.render_template(
            #         "_update-done.html", message=message)                    
            #     msg = announcer.format_sse(data=data, event='sync-done')
            #     announcer.announce(msg)
            #     announcer.close()

            # Only releases since previous sync (if any)
            # if last_log:
            #     releases = models.get_downloadable_releases(last_log.timestamp)
            #     bt.torrent_worker.add_torrents(releases)
            pass

        sync.sync_worker = sync.SyncWorker(app.config["API_CLIENT_ID"], done_callback=on_update_done)

        # Do not start workers while testing
        if not app.config['TESTING']:
            sync.sync_worker.start()     
            if app.config.get('TORRENT_ENABLED', False):
                download_dir = app.config.get('TORRENT_DOWNLOAD_DIR', '')
                if download_dir and not Path(download_dir).exists():
                    app.logger.warning(f"Torrent download directory '{download_dir}' does not exist, fallback to user home")
                    del app.config['TORRENT_DOWNLOAD_DIR']
                bt.torrent_worker = bt.BitTorrentClient()
                bt.torrent_worker.resume_torrents()
                bt.torrent_worker.start()

    def handle_shutdown_signal(s, _):
        save_config(data_dir, app)
        app.logger.debug(f"Got signal {s}, now stop workers...")
        shutdown_workers(app)
        app.logger.info("All workers stopped, exiting now")
        sys.exit()

    # Install handlers on this thread only if running within the flask dev server/waitress process
    if not app_dir:
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGHUP):
            signal.signal(s, handle_shutdown_signal)

    return app

def shutdown_workers(app):
    # Shutdown all worker threads
    for worker in [sync.sync_worker, bt.torrent_worker]:        
        if worker:
            worker.abort()
            if worker.is_alive():
                app.logger.debug(f"Waiting for {worker.name} #{id(worker)} to finish...")
                worker.join(MAX_WORKER_TIMEOUT)


def get_default_config():
    return {"API_CLIENT_ID": uuid.uuid4().hex}

def save_config(data_dir, app):
    # Save Videobox fields only 
    config = {
        'API_CLIENT_ID': app.config['API_CLIENT_ID'],        
    }
    torrent_fields = app.config.get_namespace('TORRENT_', lowercase=False, trim_namespace=False)
    config.update(torrent_fields)
    config_path = os.path.join(data_dir, CONFIG_FILENAME)    
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)    

@click.command()
@click.option('--host', help='Hostname or IP address on which to listen, default is 0.0.0.0, which means "all IP addresses on this host".', default="0.0.0.0")
@click.option('--port', help='TCP port on which to listen, default is 8080', type=int, default=8080)
def serve(host, port):
    print(f'Videobox has started. Point your browser to http://{"localhost" if host == "0.0.0.0" else host}:{port} to use the web interface.')
    waitress.serve(create_app(), host=host, port=port, threads=8)
