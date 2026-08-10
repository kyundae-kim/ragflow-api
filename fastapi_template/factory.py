from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi_template.core.config import EnvConfig, load_settings
from fastapi_template.core.exceptions import register_exception_handlers
from fastapi_template.dependencies.security import setup_auth_provider
from fastapi_template.dependencies.database import setup_db_engine
from fastapi_template.dependencies.storage import setup_minio_client
from fastapi_template.services.logging import setup_logging
from fastapi_template.routes import include_routes
from fastapi_template.dependencies.config import setup_settings, setup_config


def create_app() -> FastAPI:
    config = EnvConfig()
    settings = load_settings(config.config_path)

    setup_logging(config=config.logging)
    logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "Application startup",
            extra={"environment": config.env.value},
        )

        setup_config(app=app, config=config)
        setup_settings(app=app, settings=settings)
        setup_auth_provider(app=app, config=config.keycloak)
        setup_db_engine(app=app, config=config.db)
        setup_minio_client(app=app, config=config.minio)

        yield

        # 앱 종료 동작
        app.state.db_engine.dispose()

    app = FastAPI(lifespan=lifespan, root_path=config.root_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=settings.cors.credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    include_routes(app)
    register_exception_handlers(app)
    
    return app
