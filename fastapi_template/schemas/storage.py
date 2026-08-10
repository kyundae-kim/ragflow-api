from pydantic import BaseModel, Field


class StorageStatusResponse(BaseModel):
    status: str = Field(..., description="MinIO connectivity status")
    endpoint: str = Field(..., description="Configured MinIO endpoint")
    bucket: str = Field(..., description="Default bucket name")


class BucketListResponse(BaseModel):
    buckets: list[str] = Field(..., description="List of bucket names on the MinIO server")
