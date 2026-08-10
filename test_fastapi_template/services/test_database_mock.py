"""Unit tests for services.database – all external calls are mocked."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from fastapi_template.services.database import (
    create_db_engine,
    check_database_connection,
    get_database_version,
)


# ---------------------------------------------------------------------------
# create_db_engine
# ---------------------------------------------------------------------------

def test_create_db_engine_calls_create_engine_with_url():
    mock_config = MagicMock()
    mock_config.db.sqlalchemy_database_url = "postgresql://user:pass@localhost/db"
    mock_config.db.echo = False

    with patch("fastapi_template.services.database.create_engine") as mock_create:
        create_db_engine(mock_config)

    mock_create.assert_called_once_with(
        "postgresql://user:pass@localhost/db",
        echo=False,
        pool_pre_ping=True,
    )


# ---------------------------------------------------------------------------
# check_database_connection
# ---------------------------------------------------------------------------

def test_check_database_connection_returns_true():
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value = None

    assert check_database_connection(engine) is True


def test_check_database_connection_returns_false_on_sqlalchemy_error():
    engine = MagicMock()
    engine.connect.side_effect = SQLAlchemyError("connection refused")

    assert check_database_connection(engine) is False


# ---------------------------------------------------------------------------
# get_database_version
# ---------------------------------------------------------------------------

def test_get_database_version_returns_version_string():
    expected = "PostgreSQL 16.3 on x86_64-pc-linux-gnu"

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = expected

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value = mock_result

    version = get_database_version(engine)

    assert version == expected
