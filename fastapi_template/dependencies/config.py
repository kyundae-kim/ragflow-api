from fastapi import Request, FastAPI

from fastapi_template.core.config import ServiceSettings, EnvConfig


def setup_config(app: FastAPI, config: EnvConfig):
    """Set environment configuration in the app state."""
    app.state.config = config


def get_config(request: Request) -> EnvConfig:
    """Dependency to access environment configuration."""
    return request.app.state.config


def setup_settings(app: FastAPI, settings: ServiceSettings):
    """Set application settings in the app state."""
    app.state.settings = settings


def get_settings(request: Request) -> ServiceSettings:
    """Dependency to access application settings."""
    return request.app.state.settings
