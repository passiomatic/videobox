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
    # Check main homepage sections
    assert b'Featured series' in r.data 
    assert b'Popular tags' in r.data 
    # Check footer
    assert b'This is Videobox' in r.data 

def test_tag_index(client):  
    r = get(client, '/tag')
    assert r.status_code == 200
    # Check main categories
    assert b'Action &amp; Adventure' in r.data 
    assert b'Animation' in r.data 
    assert b'Comedy' in r.data 

def test_tag_detail(client):  
    r = get(client, '/tag/action')
    assert r.status_code == 200
    assert b'Action &amp; Adventure' in r.data 

# def test_search(client):  
#     r = get(client, '/search', query_string={'query': 'simpsons'})
#     assert r.status_code == 200
#     assert b'The Simpsons' in r.data 

# --------------
#  Helpers 
# --------------

def get(client, path, query_string=None, headers=None):
    return client.get(path, query_string=(query_string or {}), headers=(headers or {}))

def post(client, path, form=None, query_string=None, headers=None):
    return client.post(path, data=(form or {}), query_string=(query_string or {}), headers=(headers or {}))
