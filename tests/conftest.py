from pathlib import Path
import pytest
from videobox import create_app

TEST_DIR = Path(__file__).parent

class TestingConfig(object):
    DATABASE_URL = 'sqlite:///:memory:'   
    API_CLIENT_ID = '123e4567-e89b-12d3-a456-426614174000'
    TESTING = True

@pytest.fixture()
def app():
    return create_app(config_class=TestingConfig)