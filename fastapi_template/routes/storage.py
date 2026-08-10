from fastapi import APIRouter, Depends, HTTPException
from minio import Minio

from fastapi_template.core.config import EnvConfig
from fastapi_template.dependencies.config import get_config
from fastapi_template.dependencies.storage import get_minio_client
from fastapi_template.schemas.storage import BucketListResponse, StorageStatusResponse
from fastapi_template.core.storage import check_minio_connection, list_buckets


router = APIRouter()


@router.get("/storage/ping", tags=["Storage"], response_model=StorageStatusResponse)
def storage_ping(
    client: Minio = Depends(get_minio_client),
    config: EnvConfig = Depends(get_config),
):
    if not check_minio_connection(client, config.minio.bucket):
        raise HTTPException(status_code=503, detail="MinIO is not reachable")

    return StorageStatusResponse(
        status="ready",
        endpoint=config.minio.endpoint,
        bucket=config.minio.bucket,
    )


@router.get("/storage/buckets", tags=["Storage"], response_model=BucketListResponse)
def storage_list_buckets(client: Minio = Depends(get_minio_client)):
    buckets = list_buckets(client)
    return BucketListResponse(buckets=buckets)
