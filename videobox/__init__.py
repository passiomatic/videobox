"""
Videobox package.
"""

__version__ = "0.6.0"

import sys
import os
import signal
from pathlib import Path
import click
from flask import Flask
import sqlite3
import waitress
import uuid
import videobox.models as models
import videobox.filters as filters
from .main import bp as main_blueprint
from videobox.main.announcer import announcer
import videobox.sync as sync
import tomli_w
try:
    import tomllib as toml  # Python 3.11+
except ImportError:
    import tomli as toml

DATABASE_FILENAME = 'library.db'
CONFIG_FILENAME = 'config.toml'
DEFAULT_DATA_DIR = Path.home().joinpath(".videobox")

def create_app(base_dir=None, data_dir=None, config_class=None):
    if base_dir:
        template_folder=os.path.join(base_dir, "templates")
        static_folder=os.path.join(base_dir, "static")
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__)

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

    # Make sure db schema is updated but not while testing
    if not app.config['TESTING']:
        migrate_count = models.setup()
        if migrate_count:
            app.logger.debug(f"Added/updated {migrate_count} database schema fields")

    app.logger.debug(f"Using SQLite {sqlite3.sqlite_version} with database {app.config['DATABASE_URL']}")

    # Register main app routes
    app.register_blueprint(main_blueprint)

    # Register custom template filters
    filters.init_app(app)

    def handle_signal(s, frame):
        app.logger.debug(f"Got signal {s}, now stop workers...")
        sync.sync_worker.abort()
        # If worker is doing sync join and wait for a bit
        if sync.sync_worker.is_alive():
            sync.sync_worker.join(10)
        sys.exit()
    
    # Install handlers on this thread only if running within the waitress process
    if not base_dir:
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGHUP):
            signal.signal(s, handle_signal)

    with app.app_context():
        def on_update_progress(message):
            msg = announcer.format_sse(data=message, event='sync-progress')
            announcer.announce(msg)

        def on_update_done(message, alert):
            # @@TODO save alert
            msg = announcer.format_sse(data=message, event='sync-done')
            announcer.announce(msg)
            announcer.close()
            
        # Start immediately
        sync.sync_worker = sync.SyncWorker(app.config["API_CLIENT_ID"], progress_callback=on_update_progress, done_callback=on_update_done)
        # Do not keep syncing while testing
        if not app.config['TESTING']:
            sync.sync_worker.start()

    return app



def get_default_config():
    return {"API_CLIENT_ID": uuid.uuid4().hex}

@click.command()
@click.option('--host', help='Hostname or IP address on which to listen, default is 0.0.0.0, which means "all IP addresses on this host".', default="0.0.0.0")
@click.option('--port', help='TCP port on which to listen, default is 8080', type=int, default=8080)
def serve(host, port):
    print(f'Server started. Point your browser to http://{host}:{port} to use the web interface.')
    waitress.serve(create_app(), host=host, port=port, threads=8)

def run_app(base_dir, data_dir, port):
    """
    Entry point for macOS app
    """
    #print(f'App server started on port {port}')
    waitress.serve(create_app(base_dir=base_dir, data_dir=data_dir), host='127.0.0.1', port=port, threads=8)
