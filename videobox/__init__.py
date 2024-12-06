"""
Videobox package.
"""

__version__ = "0.7.3"

import sys
import os
import signal
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
        def on_update_progress(message):
            data = flask.render_template(
                "_update-progress.html", message=message)            
            msg = announcer.format_sse(data=data, event='sync-progress')
            announcer.announce(msg)

        def on_update_done(message, alert):
            # @@TODO save alert
            data = flask.render_template(
                "_update-done.html", message=message)                    
            msg = announcer.format_sse(data=data, event='sync-done')
            announcer.announce(msg)
            announcer.close()

        # Start immediately
        sync.sync_worker = sync.SyncWorker(app.config["API_CLIENT_ID"], progress_callback=on_update_progress, done_callback=on_update_done)
        # Do not keep syncing while testing
        if not app.config['TESTING']:
            sync.sync_worker.start()

    def handle_shutdown_signal(s, _):
        app.logger.debug(f"Got signal {s}, now stop workers...")
        shutdown_workers(app)
        sys.exit()

    # Install handlers on this thread only if running within the flask dev server/waitress process
    if not app_dir:
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGHUP):
            signal.signal(s, handle_shutdown_signal)

    return app

def shutdown_workers(app):
    # Shutdown all worker threads
    for worker in [sync.sync_worker]:        
        if worker:
            worker.abort()
            if worker.is_alive():
                app.logger.debug(f"Waiting for {worker.name} #{id(worker)} thread to finish work...")
                worker.join(MAX_WORKER_TIMEOUT)


def get_default_config():
    return {"API_CLIENT_ID": uuid.uuid4().hex}

@click.command()
@click.option('--host', help='Hostname or IP address on which to listen, default is 0.0.0.0, which means "all IP addresses on this host".', default="0.0.0.0")
@click.option('--port', help='TCP port on which to listen, default is 8080', type=int, default=8080)
def serve(host, port):
    print(f'Videobox has started. Point your browser to http://{"localhost" if host == "0.0.0.0" else host}:{port} to use the web interface.')
    waitress.serve(create_app(), host=host, port=port, threads=8)
