from datetime import datetime, timezone
from pathlib import Path
from peewee import fn
import json
import pytest
from videobox import create_app
import videobox.sync as sync
from videobox.models import db_wrapper, Tag, Series, SeriesTag, Episode, Release
import videobox.models as models
from .conftest import TestingConfig

TEST_DIR = Path(__file__).parent

@pytest.fixture()
def app():
    app = create_app(data_dir=TEST_DIR, config_class=TestingConfig)
    with open(TEST_DIR.joinpath("test-data.sql"), 'r') as f:
        # https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.executescript
        sql = f.read()
        db_wrapper.database.connection().executescript(sql)

    yield app

    db_wrapper.database.connection().close()


def test_save_tags(app):
    with open(TEST_DIR.joinpath("sync", 'tags.json'), "r") as json_file:
        json_data = json.load(json_file)
        assert models.save_tags(app, json_data) == len(json_data)
        assert Tag.get_or_none(id=json_data[0]['id'])

def test_save_series(app):
    with open(TEST_DIR.joinpath("sync", 'series.json'), "r") as json_file:
        json_data = json.load(json_file)
        assert models.save_series(app, json_data) == len(json_data)
        assert Series.get_or_none(id=json_data[0]['id'])

def test_save_series_tags(app):
    with open(TEST_DIR.joinpath("sync", 'series-tags.json'), "r") as json_file:
        json_data = json.load(json_file)
        assert SeriesTag.get_or_none(SeriesTag.series==json_data[0]['series_id'], SeriesTag.tag==json_data[0]['tag_id'])

def test_save_episodes(app):
    with open(TEST_DIR.joinpath("sync", 'episodes.json'), "r") as json_file:
        json_data = json.load(json_file)
        assert models.save_episodes(app, json_data) == len(json_data)
        assert Episode.get_or_none(id=json_data[0]['id'])

def test_save_releases(app):
    with open(TEST_DIR.joinpath("sync", 'releases.json'), "r") as json_file:
        json_data = json.load(json_file)
        assert models.save_releases(app, json_data) == len(json_data)
        assert Release.get_or_none(id=json_data[0]['id'])
