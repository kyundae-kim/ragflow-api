"""Integration tests for core.storage – require a live MinIO instance."""
import pytest
from fastapi_template.core.config import EnvConfig
from fastapi_template.core.storage import (
    create_minio_client,
    check_minio_connection,
    ensure_bucket_exists,
    list_buckets,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def minio_client():
    config = EnvConfig()
    return create_minio_client(config.minio)


def test_check_minio_connection_live(minio_client):
    """MinIO 서버에 실제로 연결하여 버킷 접근 가능 여부 확인."""
    config = EnvConfig()
    assert check_minio_connection(minio_client, config.minio.bucket) is True


def test_ensure_bucket_exists_live(minio_client):
    """버킷이 없으면 생성하고, 이미 있으면 오류 없이 통과."""
    config = EnvConfig()
    ensure_bucket_exists(minio_client, config.minio.bucket)
    assert minio_client.bucket_exists(config.minio.bucket) is True


def test_list_buckets_live(minio_client):
    """버킷 목록을 반환하며 최소 하나 이상의 버킷이 존재."""
    config = EnvConfig()
    ensure_bucket_exists(minio_client, config.minio.bucket)
    buckets = list_buckets(minio_client)
    assert isinstance(buckets, list)
    assert config.minio.bucket in buckets
