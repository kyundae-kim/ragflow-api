"""Integration tests for services.database – require a live PostgreSQL instance."""
import pytest

from fastapi_template.core.config import EnvConfig, load_settings
from fastapi_template.services.database import (
    create_db_engine,
    check_database_connection,
    get_database_version,
)


settings = EnvConfig()


@pytest.fixture(scope="module")
def db_config():
    load_settings(settings.config_path)
    return settings.db


@pytest.fixture(scope="module")
def engine(db_config):
    eng = create_db_engine(EnvConfig())
    yield eng
    eng.dispose()


def test_check_database_connection(engine):
    """실제 PostgreSQL 연결 후 True 반환 확인."""
    assert check_database_connection(engine) is True


def test_get_database_version(engine):
    """버전 문자열에 'PostgreSQL' 포함 확인."""
    version = get_database_version(engine)
    assert isinstance(version, str)
    assert "PostgreSQL" in version
