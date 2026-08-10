from fastapi import FastAPI, Request
from minio import Minio

from fastapi_template.core.config import MinioConfig
from fastapi_template.core.storage import create_minio_client


def setup_minio_client(app: FastAPI, config: MinioConfig) -> None:
    """Initialise the MinIO client and attach it to the app state."""
    app.state.minio_client = create_minio_client(config)


def get_minio_client(request: Request) -> Minio:
    """FastAPI dependency – returns the shared MinIO client."""
    return request.app.state.minio_client
