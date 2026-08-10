from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
import logging
from urllib.parse import quote_plus


class LoggingLevel(str, Enum):
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"
    PORD = "prod"


class DatabaseAuthMethod(str, Enum):
    PASSWORD = "password"
    TRUST = "trust"


class DatabaseConfig(BaseModel):
    """PostgreSQL connection and authentication settings."""
    host: str = Field(default="postgres")
    port: int = Field(default=5432)
    name: str = Field(default="postgres")
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")
    auth_method: DatabaseAuthMethod = Field(default=DatabaseAuthMethod.PASSWORD)
    sslmode: str = Field(default="prefer")
    connect_timeout: int = Field(default=5)
    echo: bool = Field(default=False)
    url: str | None = Field(default=None)

    @property
    def sqlalchemy_database_url(self) -> str:
        """Build SQLAlchemy database URL from settings."""
        if self.url:
            return self.url

        if self.auth_method == DatabaseAuthMethod.TRUST:
            return (
                f"postgresql+psycopg://{self.host}:{self.port}/{self.name}"
                f"?sslmode={self.sslmode}&connect_timeout={self.connect_timeout}"
            )

        encoded_user = quote_plus(self.user)
        encoded_password = quote_plus(self.password)
        return (
            "postgresql+psycopg://"
            f"{encoded_user}:{encoded_password}@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.sslmode}&connect_timeout={self.connect_timeout}"
        )
    

class KeycloakConfig(BaseModel):
    http_url: HttpUrl = Field(default="http://localhost:8080/")
    manage_url: HttpUrl = Field(default="http://localhost:9000/")
    realm: str = Field(default="restapi")
    client_id: str = Field(default="fastapi")
    client_secret: str | None = Field(default=None)


class MinioConfig(BaseModel):
    """MinIO object storage connection settings."""
    endpoint: str = Field(default="minio:9000")
    access_key: str = Field(default="admin")
    secret_key: str = Field(default="password")
    secure: bool = Field(default=False)
    bucket: str = Field(default="default")


class LoggingConfig(BaseModel):
    level: LoggingLevel = Field(default=LoggingLevel.DEBUG)


class EnvConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    env: Environment = Field(default=Environment.DEV)
    config_path: str = Field(default=".devcontainer/config.yaml")
    root_path: str = Field(default="/")
    token_url: str = Field(default="token")

    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    keycloak_username: str = Field(default="test")
    keycloak_password: str = Field(default="test")

    keycloak: KeycloakConfig = Field(default_factory=KeycloakConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    minio: MinioConfig = Field(default_factory=MinioConfig)


class CorsSettings(BaseModel):
    origins: list[str] = Field(default_factory=lambda: ["*"])
    credentials: bool = Field(default=False)

    @field_validator("origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


class AuthSettings(BaseModel):
    verify_jwt: bool = Field(default=True)
    allow_insecure_jwt_decode: bool = Field(default=False)
    use_introspection: bool = Field(default=False)


class ServiceSettings(BaseSettings):
    cors: CorsSettings = Field(default_factory=CorsSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


logger = logging.getLogger(__name__)


def load_settings(path: str) -> ServiceSettings:
    '''Utility function to load settings from a specific YAML file path.'''

    try:
        yaml_source = YamlConfigSettingsSource(ServiceSettings, yaml_file=path)
        return ServiceSettings.model_validate(yaml_source())
    except Exception as e:
        logger.info("Failed to load settings from %s: %s", path, e)
        return ServiceSettings()
