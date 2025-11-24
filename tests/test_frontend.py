from pathlib import Path
import pytest
from videobox import create_app
from videobox.models import db_wrapper, setup, Series, Release
from .conftest import TestingConfig

TEST_DIR = Path(__file__).parent

@pytest.fixture()
def app_empty_db():
    app = create_app(data_dir=TEST_DIR, config_class=TestingConfig)
    setup()

    yield app

    db_wrapper.database.connection().close()

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

@pytest.fixture()
def client_empty_db(app_empty_db):
    return app_empty_db.test_client()

def test_home(client):  
    r = client.get('/')
    assert r.status_code == 200
    # Check main homepage sections
    assert b'Featured series' in r.data 
    assert b'Popular genres' in r.data 
    # Check footer
    assert b'This is Videobox' in r.data 

def test_first_import(client_empty_db):  
    r = client_empty_db.get('/')
    assert r.status_code == 200
    # Check main homepage sections
    assert b'Videobox is importing' in r.data 

def test_tag_index(client):  
    r = client.get('/tag')
    assert r.status_code == 200
    # Check main categories
    assert b'Action &amp; Adventure' in r.data 
    assert b'Animation' in r.data 
    assert b'Comedy' in r.data 

def test_tag_detail(client):  
    r = client.get('/tag/action')
    assert r.status_code == 200
    assert b'Action &amp; Adventure' in r.data 

def test_series_detail(client):  
    # Grab a series 
    series = Series.select().get_or_none()    
    r = client.get(f'/series/{series.id}')
    assert r.status_code == 200
    assert series.name in r.text

def test_series_detail_follow(client):
    # Grab a series to follow   
    series = Series.select().get_or_none()
    r = client.post(f'/series/follow/{series.id}', data={'following': 1})
    assert r.status_code == 200
    assert b'Unfollow' in r.data     

def test_search(client):  
    r = client.get('/search', query_string={'query': 'The Simpsons'})
    # Check for single or multiple matches
    assert r.status_code in [302, 200]

def test_search_info_hash(client):  
    # Grab a release
    release = Release.select().limit(1)[0]
    r = client.get('/search', query_string={'query': release.info_hash})
    assert r.status_code == 302

def test_suggest_with_ascii(client):  
    r = client.get('/suggest', query_string={'query': 'Simpsons'})
    assert r.status_code == 200
    assert b'The Simpsons' in r.data

def test_suggest_with_unicode(client):  
    r = client.get('/suggest', query_string={'query': 'Shōgun'})
    assert r.status_code == 200
    assert 'Shōgun' in r.text

def test_suggest_with_unicode_2(client):  
    r = client.get('/suggest', query_string={'query': 'Shogun'})
    assert r.status_code == 200
    assert 'Shōgun' in r.text