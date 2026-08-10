from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from fastapi_template.core.config import EnvConfig


def create_db_engine(config: EnvConfig) -> Engine:
    return create_engine(
        config.db.sqlalchemy_database_url,
        echo=config.db.echo,
        pool_pre_ping=True,
    )


def check_database_connection(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def get_database_version(engine: Engine) -> str:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))
        version = result.scalar_one()
    return str(version)
