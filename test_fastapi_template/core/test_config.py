from fastapi_template.core.config import (
    DatabaseAuthMethod,
    DatabaseConfig,
    EnvConfig,
    LoggingLevel,
)


def test_sqlalchemy_database_url_with_password_auth():
    db_settings = DatabaseConfig(
        host="db.local",
        port=5432,
        name="app",
        user="app_user",
        password="s3cret!",
        auth_method=DatabaseAuthMethod.PASSWORD,
        sslmode="require",
        connect_timeout=10,
    )

    assert db_settings.sqlalchemy_database_url == (
        "postgresql+psycopg://app_user:s3cret%21@db.local:5432/app"
        "?sslmode=require&connect_timeout=10"
    )


def test_sqlalchemy_database_url_with_trust_auth():
    db_settings = DatabaseConfig(
        host="db.internal",
        port=5433,
        name="app",
        auth_method=DatabaseAuthMethod.TRUST,
    )

    assert db_settings.sqlalchemy_database_url.startswith("postgresql+psycopg://db.internal:5433/app")


def test_sqlalchemy_database_url_uses_database_url_override():
    db_settings = DatabaseConfig(url="postgresql+psycopg://custom-host:5432/custom-db")

    assert db_settings.sqlalchemy_database_url == "postgresql+psycopg://custom-host:5432/custom-db"


def test_env_config_uses_default_logging_level(monkeypatch):
    monkeypatch.delenv("LOGGING__LEVEL", raising=False)

    config = EnvConfig()

    assert config.logging.level == LoggingLevel.DEBUG


def test_env_config_reads_logging_level_from_env(monkeypatch):
    monkeypatch.setenv("LOGGING__LEVEL", "INFO")

    config = EnvConfig()

    assert config.logging.level == LoggingLevel.INFO
