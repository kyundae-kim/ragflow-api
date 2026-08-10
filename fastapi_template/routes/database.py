from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine

from fastapi_template.core.config import EnvConfig
from fastapi_template.dependencies.config import get_config
from fastapi_template.dependencies.database import get_db_engine
from fastapi_template.schemas.database import DatabaseStatusResponse, DatabaseVersionResponse
from fastapi_template.services.database import check_database_connection, get_database_version


router = APIRouter()


@router.get("/db/example/ping", tags=["Database"], response_model=DatabaseStatusResponse)
def database_ping(
    engine: Engine = Depends(get_db_engine),
    config: EnvConfig = Depends(get_config),
):
    if not check_database_connection(engine):
        raise HTTPException(status_code=503, detail="Database is not reachable")

    return DatabaseStatusResponse(
        status="ready",
        auth_method=config.db.auth_method.value,
    )


@router.get("/db/example/version", tags=["Database"], response_model=DatabaseVersionResponse)
def database_version(engine: Engine = Depends(get_db_engine)):
    version = get_database_version(engine)
    return DatabaseVersionResponse(version=version)
