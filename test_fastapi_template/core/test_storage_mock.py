"""Unit tests for core.storage – all external calls are mocked."""
import pytest
from unittest.mock import MagicMock, patch

from fastapi_template.core.storage import (
    create_minio_client,
    check_minio_connection,
    ensure_bucket_exists,
    list_buckets,
)


# ---------------------------------------------------------------------------
# create_minio_client
# ---------------------------------------------------------------------------

def test_create_minio_client_calls_minio_with_config():
    config = MagicMock()
    config.endpoint = "minio:9000"
    config.access_key = "admin"
    config.secret_key = "password"
    config.secure = False

    with patch("fastapi_template.core.storage.Minio") as mock_minio:
        create_minio_client(config)

    mock_minio.assert_called_once_with(
        endpoint="minio:9000",
        access_key="admin",
        secret_key="password",
        secure=False,
    )


# ---------------------------------------------------------------------------
# check_minio_connection
# ---------------------------------------------------------------------------

def test_check_minio_connection_returns_true():
    client = MagicMock()
    client.bucket_exists.return_value = True

    assert check_minio_connection(client, "default") is True
    client.bucket_exists.assert_called_once_with("default")


def test_check_minio_connection_returns_false_on_exception():
    client = MagicMock()
    client.bucket_exists.side_effect = Exception("connection refused")

    assert check_minio_connection(client, "default") is False


# ---------------------------------------------------------------------------
# ensure_bucket_exists
# ---------------------------------------------------------------------------

def test_ensure_bucket_exists_creates_bucket_when_not_present():
    client = MagicMock()
    client.bucket_exists.return_value = False

    ensure_bucket_exists(client, "mybucket")

    client.make_bucket.assert_called_once_with("mybucket")


def test_ensure_bucket_exists_skips_creation_when_already_present():
    client = MagicMock()
    client.bucket_exists.return_value = True

    ensure_bucket_exists(client, "mybucket")

    client.make_bucket.assert_not_called()


# ---------------------------------------------------------------------------
# list_buckets
# ---------------------------------------------------------------------------

def test_list_buckets_returns_bucket_names():
    bucket_a = MagicMock()
    bucket_a.name = "alpha"
    bucket_b = MagicMock()
    bucket_b.name = "beta"

    client = MagicMock()
    client.list_buckets.return_value = [bucket_a, bucket_b]

    result = list_buckets(client)

    assert result == ["alpha", "beta"]


def test_list_buckets_empty():
    client = MagicMock()
    client.list_buckets.return_value = []

    assert list_buckets(client) == []
