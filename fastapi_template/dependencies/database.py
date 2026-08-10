from fastapi import Request, FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

from fastapi_template.core.config import DatabaseConfig


def setup_db_engine(app: FastAPI, config: DatabaseConfig):
    """Set the database engine in the app state."""
    app.state.db_engine = create_engine(
        config.sqlalchemy_database_url,
        echo=config.echo,
        pool_pre_ping=True,
    )


def get_db_engine(request: Request) -> Engine:
    return request.app.state.db_engine
