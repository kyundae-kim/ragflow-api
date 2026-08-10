from minio import Minio

from fastapi_template.core.config import MinioConfig


def create_minio_client(config: MinioConfig) -> Minio:
    """Create a MinIO client from configuration."""
    return Minio(
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=config.secure,
    )


def check_minio_connection(client: Minio, bucket: str) -> bool:
    """Return True if the MinIO server is reachable."""
    try:
        return client.bucket_exists(bucket)
    except Exception:
        return False


def ensure_bucket_exists(client: Minio, bucket: str) -> None:
    """Create the bucket if it does not already exist."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def list_buckets(client: Minio) -> list[str]:
    """Return a list of bucket names available on the MinIO server."""
    return [b.name for b in client.list_buckets()]
