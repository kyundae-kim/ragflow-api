from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any, Protocol
from urllib.parse import urlsplit

import jwt
from rag_system_core import AuthenticatedUser


class AuthenticationError(Exception):
    """Raised when a bearer token cannot be authenticated."""


class AuthenticationUnavailableError(AuthenticationError):
    """Raised when the identity provider cannot validate a bearer token."""


class Authenticator(Protocol):
    def authenticate(self, token: str) -> AuthenticatedUser: ...


class SigningKey(Protocol):
    key: Any


class JwkClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> SigningKey: ...


@dataclass(frozen=True, slots=True)
class KeycloakSettings:
    base_url: str
    realm: str
    client_id: str
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        parsed_url = urlsplit(self.base_url)
        if parsed_url.scheme not in {"http", "https"} or parsed_url.hostname is None:
            raise ValueError("Keycloak base_url must use http or https")
        if parsed_url.username is not None or parsed_url.password is not None:
            raise ValueError("Keycloak base_url must not contain credentials")
        if (
            parsed_url.scheme == "http"
            and not self.allow_insecure_http
            and not _is_loopback_host(parsed_url.hostname)
        ):
            raise ValueError("Keycloak base_url must use HTTPS outside loopback development")
        if not self.realm.strip():
            raise ValueError("Keycloak realm is required")
        if not self.client_id.strip():
            raise ValueError("Keycloak client_id is required")

    @property
    def issuer(self) -> str:
        return f"{self.base_url.rstrip('/')}/realms/{self.realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"


def _is_loopback_host(hostname: str) -> bool:
    if hostname.rstrip(".").lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


class KeycloakAuthenticator:
    def __init__(
        self,
        *,
        settings: KeycloakSettings,
        jwk_client: JwkClient | None = None,
    ) -> None:
        self.settings = settings
        self.jwk_client = jwk_client or jwt.PyJWKClient(settings.jwks_url)

    def authenticate(self, token: str) -> AuthenticatedUser:
        try:
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.client_id,
                issuer=self.settings.issuer,
                options={"require": ["exp", "sub", "typ"]},
            )
            return _user_from_claims(claims)
        except jwt.PyJWKClientConnectionError as error:
            raise AuthenticationUnavailableError("Identity provider is unavailable") from error
        except (jwt.PyJWTError, jwt.PyJWKClientError, KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("Bearer token validation failed") from error


def _user_from_claims(claims: dict[str, Any]) -> AuthenticatedUser:
    if claims.get("typ") != "Bearer":
        raise ValueError("Token must be a Keycloak bearer access token")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Token subject is required")

    realm_access = claims.get("realm_access")
    realm_roles = _roles(realm_access.get("roles")) if isinstance(realm_access, dict) else []

    client_roles: dict[str, list[str]] = {}
    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        for client, access in resource_access.items():
            if isinstance(client, str) and isinstance(access, dict):
                client_roles[client] = _roles(access.get("roles"))

    return AuthenticatedUser(
        sub=subject,
        preferred_username=_optional_string(claims.get("preferred_username")),
        email=_optional_string(claims.get("email")),
        given_name=_optional_string(claims.get("given_name")),
        family_name=_optional_string(claims.get("family_name")),
        name=_optional_string(claims.get("name")),
        realm_roles=realm_roles,
        client_roles=client_roles,
        claims=dict(claims),
    )


def _roles(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [role for role in value if isinstance(role, str)]


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
