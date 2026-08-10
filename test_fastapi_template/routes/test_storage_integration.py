"""Integration tests for routes.storage – require a live MinIO instance."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from fastapi_template.factory import create_app
from fastapi_template.core.config import EnvConfig
from fastapi_template.core.storage import create_minio_client, ensure_bucket_exists


@pytest.fixture(scope="module")
def client():
    """TestClient backed by a real MinIO; auth provider and DB are mocked out."""
    config = EnvConfig()
    real_minio = create_minio_client(config.minio)
    ensure_bucket_exists(real_minio, config.minio.bucket)

    dummy_engine = MagicMock()
    dummy_engine.dispose = MagicMock()
    mock_auth_provider = MagicMock()

    def real_setup_minio_client(app, config):
        app.state.minio_client = real_minio

    def fake_setup_db_engine(app, config):
        app.state.db_engine = dummy_engine

    def fake_setup_auth_provider(app, config):
        app.state.auth_provider = mock_auth_provider

    with (
        patch("fastapi_template.factory.setup_minio_client", side_effect=real_setup_minio_client),
        patch("fastapi_template.factory.setup_db_engine", side_effect=fake_setup_db_engine),
        patch("fastapi_template.factory.setup_auth_provider", side_effect=fake_setup_auth_provider),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c


def test_storage_ping_ready(client):
    """/storage/ping 이 실제 MinIO에 연결되어 200을 반환하는지 확인."""
    response = client.get("/storage/ping")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["endpoint"] == EnvConfig().minio.endpoint
    assert data["bucket"] == EnvConfig().minio.bucket


def test_storage_list_buckets(client):
    """/storage/buckets 가 실제 버킷 목록을 반환하는지 확인."""
    response = client.get("/storage/buckets")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["buckets"], list)
    assert EnvConfig().minio.bucket in data["buckets"]
