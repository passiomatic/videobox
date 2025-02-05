from pathlib import Path
import pytest
from videobox import create_app
from videobox.models import db_wrapper
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


@pytest.fixture()
def client(app):
    return app.test_client()

def test_scpd_content_directory(client):  
    r = client.get('/dlna/scpd-content-directory.xml')
    assert r.status_code == 200

def test_scpd_connection_manager(client):  
    r = client.get('/dlna/scpd-connection-manager.xml')
    assert r.status_code == 200

def test_description_xml(client):   
    r = client.get('/dlna/description.xml')
    assert r.status_code == 200