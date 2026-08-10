"""Integration tests for routes.database – require a live PostgreSQL instance."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from fastapi_template.factory import create_app
from fastapi_template.services.database import create_db_engine
from fastapi_template.core.config import EnvConfig


@pytest.fixture(scope="module")
def client():
    """TestClient backed by a real PostgreSQL; Keycloak auth provider is mocked out."""
    config = EnvConfig()
    real_engine = create_db_engine(config)

    def real_setup_db_engine(app, config):
        app.state.db_engine = real_engine

    mock_auth_provider = MagicMock()

    def fake_setup_auth_provider(app, config):
        app.state.auth_provider = mock_auth_provider

    with (
        patch("fastapi_template.factory.setup_db_engine", side_effect=real_setup_db_engine),
        patch("fastapi_template.factory.setup_auth_provider", side_effect=fake_setup_auth_provider),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c

    real_engine.dispose()


def test_database_ping_ready(client):
    """/db/example/ping 이 실제 PostgreSQL에 연결되어 200을 반환하는지 확인."""
    response = client.get("/db/example/ping")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["engine"] == "postgresql"
    assert data["auth_method"] in {"password", "trust"}


def test_database_version(client):
    """/db/example/version 이 실제 PostgreSQL 버전 문자열을 반환하는지 확인."""
    response = client.get("/db/example/version")

    assert response.status_code == 200
    data = response.json()
    assert "PostgreSQL" in data["version"]
