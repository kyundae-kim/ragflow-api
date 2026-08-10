from pydantic import BaseModel, Field


class DatabaseStatusResponse(BaseModel):
    status: str = Field(..., description="Database connectivity status")
    engine: str = Field(default="postgresql", description="Database engine type")
    auth_method: str = Field(..., description="Configured database authentication method")


class DatabaseVersionResponse(BaseModel):
    version: str = Field(..., description="Database server version string")
