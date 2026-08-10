from fastapi import FastAPI


from fastapi_template.routes.auth import router as auth_router
from fastapi_template.routes.database import router as database_router
from fastapi_template.routes.health import router as healthcheck_router
from fastapi_template.routes.storage import router as storage_router


def include_routes(app: FastAPI):
    app.include_router(healthcheck_router)
    app.include_router(auth_router)
    app.include_router(database_router)
    app.include_router(storage_router)
