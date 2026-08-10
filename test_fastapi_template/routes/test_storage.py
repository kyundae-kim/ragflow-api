"""Unit tests for routes.storage – all external calls are mocked."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from fastapi_template.factory import create_app


class DummyEngine:
    def dispose(self):
        return None


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    dummy_engine = DummyEngine()
    dummy_minio = MagicMock()

    def fake_setup_db_engine(app, config):
        app.state.db_engine = dummy_engine

    def fake_setup_minio_client(app, config):
        app.state.minio_client = dummy_minio

    monkeypatch.setattr("fastapi_template.factory.setup_db_engine", fake_setup_db_engine)
    monkeypatch.setattr("fastapi_template.factory.setup_minio_client", fake_setup_minio_client)

    with TestClient(create_app()) as client:
        yield client


def test_storage_ping_ready(app, monkeypatch):
    monkeypatch.setattr(
        "fastapi_template.routes.storage.check_minio_connection",
        lambda client, bucket: True,
    )

    response = app.get("/storage/ping")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "endpoint" in data
    assert "bucket" in data


def test_storage_ping_not_ready(app, monkeypatch):
    monkeypatch.setattr(
        "fastapi_template.routes.storage.check_minio_connection",
        lambda client, bucket: False,
    )

    response = app.get("/storage/ping")

    assert response.status_code == 503
    assert response.json()["detail"] == "MinIO is not reachable"


def test_storage_list_buckets(app, monkeypatch):
    monkeypatch.setattr(
        "fastapi_template.routes.storage.list_buckets",
        lambda client: ["alpha", "beta"],
    )

    response = app.get("/storage/buckets")

    assert response.status_code == 200
    assert response.json() == {"buckets": ["alpha", "beta"]}


def test_storage_list_buckets_empty(app, monkeypatch):
    monkeypatch.setattr(
        "fastapi_template.routes.storage.list_buckets",
        lambda client: [],
    )

    response = app.get("/storage/buckets")

    assert response.status_code == 200
    assert response.json() == {"buckets": []}
