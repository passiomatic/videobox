from pathlib import Path
import pytest
from videobox import create_app

TEST_DIR = Path(__file__).parent

class TestingConfig(object):
    DATABASE_URL = 'sqlite:///:memory:'   
    TESTING = True

@pytest.fixture()
def app():
    return create_app(config_class=TestingConfig)