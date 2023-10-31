"""
Videobox package.
"""

__version__ = "0.5.0"

import os
from pathlib import Path
import click
from flask import Flask
import sqlite3
import waitress
import uuid
import videobox.models as models
import videobox.filters as filters
from .main import bp as main_blueprint
import tomli_w
try:
    import tomllib as toml  # Python 3.11+
except ImportError:
    import tomli as toml

DATABASE_FILENAME = 'library.db'
CONFIG_FILENAME = 'config.toml'
APP_DIR = Path.home().joinpath(".videobox")


def create_app(config_class=None):
    app = Flask(__name__)
    os.makedirs(APP_DIR, exist_ok=True)

    if config_class:    
        app.config.from_object(config_class)
    else:
        app.config['DATABASE_URL'] = f'sqlite:///{APP_DIR.joinpath(DATABASE_FILENAME)}' 
        config_path = os.path.join(APP_DIR, CONFIG_FILENAME)
        if app.config.from_file(config_path, load=toml.load, text=False, silent=True):
            app.logger.debug(f"Using configuration file found in {APP_DIR}")
        else:
            config = get_default_config()
            app.config.from_mapping(config)
            with open(config_path, "wb") as f:
                tomli_w.dump(config, f)

    # Initialize Flask extensions here
    models.db_wrapper.init_app(app)
    models.db_wrapper.database.pragma('foreign_keys', 1, permanent=True)
    models.db_wrapper.database.pragma('journal_mode', 'wal', permanent=True)
    app.logger.debug(f"Using SQLite version {sqlite3.sqlite_version}")

    # Make sure db schema is updated 
    models.setup()
    app.logger.debug(f"Using database found in {APP_DIR}")

    # Register main app routes
    app.register_blueprint(main_blueprint)

    # Register custom template filters
    filters.init_app(app)

    return app

def get_default_config():
    return {"API_CLIENT_ID": uuid.uuid1().hex}

@click.command()
@click.option('--host', help='Hostname or IP address on which to listen, default is 0.0.0.0, which means "all IP addresses on this host".', default="0.0.0.0")
@click.option('--port', help='TCP port on which to listen, default is 8080', type=int, default=8080)
def serve(host, port):
    print(f'Server started. Point your browser to http://{host}:{port} to use the web interface.')
    waitress.serve(create_app(), host=host, port=port, threads=8)