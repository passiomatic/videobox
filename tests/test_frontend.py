from pathlib import Path
import pytest
from videobox import create_app
from videobox.models import db_wrapper
from videobox import TestingConfig

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

def test_home(client):  
    r = get(client, '/')
    assert r.status_code == 200    

# --------------
#  Helpers 
# --------------

def get(client, path, query_string=None, headers=None):
    return client.get(path, query_string=(query_string or {}), headers=(headers or {}))

def post(client, path, form=None, query_string=None, headers=None):
    return client.post(path, data=(form or {}), query_string=(query_string or {}), headers=(headers or {}))