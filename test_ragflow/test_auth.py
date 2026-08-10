from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ragflow.auth import (
    AuthenticationError,
    KeycloakAuthenticator,
    KeycloakSettings,
    SigningKey,
)


class StaticSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


class StaticJwkClient:
    def __init__(self, public_key: object) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SigningKey:
        del token
        return StaticSigningKey(self.public_key)


def test_keycloak_settings_reject_remote_plaintext_http_by_default() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        KeycloakSettings(
            base_url="http://identity.example",
            realm="docmesh",
            client_id="rag-api",
        )


def test_keycloak_settings_allow_loopback_http_for_local_development() -> None:
    settings = KeycloakSettings(
        base_url="http://127.0.0.1:8080",
        realm="docmesh",
        client_id="rag-api",
    )

    assert settings.jwks_url.startswith("http://127.0.0.1:8080/")


def test_keycloak_settings_allow_explicit_remote_http_override() -> None:
    settings = KeycloakSettings(
        base_url="http://identity.internal",
        realm="docmesh",
        client_id="rag-api",
        allow_insecure_http=True,
    )

    assert settings.jwks_url.startswith("http://identity.internal/")


def make_token(
    *,
    private_key: rsa.RSAPrivateKey,
    audience: str = "rag-api",
    issuer: str = "https://identity.example/realms/docmesh",
    expired: bool = False,
    include_expiration: bool = True,
    token_type: str = "Bearer",
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "user-a",
        "preferred_username": "alice",
        "email": "alice@example.com",
        "given_name": "Alice",
        "family_name": "Kim",
        "name": "Alice Kim",
        "realm_access": {"roles": ["reader", "writer"]},
        "resource_access": {
            "rag-api": {"roles": ["query"]},
            "other-client": {"roles": ["other"]},
        },
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "typ": token_type,
    }
    if include_expiration:
        claims["exp"] = now - timedelta(minutes=5) if expired else now + timedelta(minutes=5)
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def test_keycloak_authenticator_maps_signed_claims_to_application_user() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )

    user = authenticator.authenticate(make_token(private_key=private_key))

    assert user.sub == "user-a"
    assert user.preferred_username == "alice"
    assert user.email == "alice@example.com"
    assert user.given_name == "Alice"
    assert user.family_name == "Kim"
    assert user.name == "Alice Kim"
    assert user.realm_roles == ["reader", "writer"]
    assert user.client_roles == {
        "rag-api": ["query"],
        "other-client": ["other"],
    }
    assert user.claims["sub"] == "user-a"


def test_keycloak_authenticator_rejects_wrong_audience() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )
    token = make_token(private_key=private_key, audience="another-api")

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(token)


def test_keycloak_authenticator_rejects_wrong_issuer() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )
    token = make_token(
        private_key=private_key,
        issuer="https://attacker.example/realms/docmesh",
    )

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(token)


def test_keycloak_authenticator_requires_expiration() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )
    token = make_token(private_key=private_key, include_expiration=False)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(token)


def test_keycloak_authenticator_rejects_expired_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )
    token = make_token(private_key=private_key, expired=True)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(token)


def test_keycloak_authenticator_rejects_id_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example/",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=StaticJwkClient(private_key.public_key()),
    )
    token = make_token(private_key=private_key, token_type="ID")

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(token)


def test_keycloak_authenticator_distinguishes_jwks_outage() -> None:
    from ragflow.auth import AuthenticationUnavailableError

    class UnavailableJwkClient:
        def get_signing_key_from_jwt(self, token: str) -> SigningKey:
            del token
            raise jwt.PyJWKClientConnectionError("identity.internal leaked details")

    authenticator = KeycloakAuthenticator(
        settings=KeycloakSettings(
            base_url="https://identity.example",
            realm="docmesh",
            client_id="rag-api",
        ),
        jwk_client=UnavailableJwkClient(),
    )

    with pytest.raises(AuthenticationUnavailableError):
        authenticator.authenticate("token")
