import pytest
import httpx
import jwt
from unittest.mock import MagicMock, patch

from fastapi_template.core.security import (
    User,
    Token,
    KeycloakAuthProvider,
    extract_roles,
    extract_scopes,
)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def test_extract_roles_from_realm_access():
    payload = {"realm_access": {"roles": ["admin", "user"]}}
    assert extract_roles(payload) == {"admin", "user"}


def test_extract_roles_empty_payload():
    assert extract_roles({}) == set()


def test_extract_roles_non_list_ignored():
    assert extract_roles({"realm_access": {"roles": "admin"}}) == set()


def test_extract_scopes_from_scope_string():
    payload = {"scope": "openid profile email"}
    assert extract_scopes(payload) == {"openid", "profile", "email"}


def test_extract_scopes_from_scp_list():
    payload = {"scp": ["openid", "profile"]}
    assert extract_scopes(payload) == {"openid", "profile"}


def test_extract_scopes_empty_payload():
    assert extract_scopes({}) == set()


# ---------------------------------------------------------------------------
# KeycloakAuthProvider – construction validation
# ---------------------------------------------------------------------------

def test_keycloak_auth_provider_empty_url_raises():
    with pytest.raises(ValueError, match="URL"):
        KeycloakAuthProvider(url="", realm="realm", client_id="client")


def test_keycloak_auth_provider_no_schema_raises():
    with pytest.raises(ValueError, match="http"):
        KeycloakAuthProvider(url="keycloak:8080/", realm="realm", client_id="client")


def test_keycloak_auth_provider_no_trailing_slash_raises():
    with pytest.raises(ValueError, match="slash"):
        KeycloakAuthProvider(url="http://keycloak:8080", realm="realm", client_id="client")


def test_keycloak_auth_provider_empty_realm_raises():
    with pytest.raises(ValueError, match="realm"):
        KeycloakAuthProvider(url="http://keycloak:8080/", realm="", client_id="client")


def test_keycloak_auth_provider_empty_client_id_raises():
    with pytest.raises(ValueError, match="client_id"):
        KeycloakAuthProvider(url="http://keycloak:8080/", realm="realm", client_id="")


# ---------------------------------------------------------------------------
# Shared fixture: provider with mocked JWK client (no network calls)
# ---------------------------------------------------------------------------

@pytest.fixture
def provider():
    with patch("fastapi_template.core.security.jwt.PyJWKClient"):
        return KeycloakAuthProvider(
            url="http://keycloak:8080/",
            realm="test",
            client_id="fastapi",
        )


# ---------------------------------------------------------------------------
# to_user
# ---------------------------------------------------------------------------

def test_to_user_maps_payload_to_user(provider):
    payload = {
        "sub": "user-123",
        "preferred_username": "tester",
        "email": "tester@example.com",
        "name": "Test User",
        "realm_access": {"roles": ["admin"]},
        "scope": "openid profile",
    }
    user = provider.to_user(payload)
    assert isinstance(user, User)
    assert user.sub == "user-123"
    assert user.preferred_username == "tester"
    assert "admin" in user.roles
    assert "openid" in user.scopes


# ---------------------------------------------------------------------------
# decode_token_insecure
# ---------------------------------------------------------------------------

def test_decode_token_insecure_returns_user(provider):
    payload = {
        "sub": "user-123",
        "preferred_username": "tester",
        "email": "tester@example.com",
        "name": "Test User",
        "realm_access": {"roles": ["admin"]},
        "scope": "openid profile",
    }
    with patch("fastapi_template.core.security.jwt.decode", return_value=payload):
        user = provider.decode_token_insecure("some.jwt.token")
    assert isinstance(user, User)
    assert user.sub == "user-123"


def test_decode_token_insecure_invalid_token_raises(provider):
    with patch("fastapi_template.core.security.jwt.decode", side_effect=jwt.InvalidTokenError("bad")):
        with pytest.raises(jwt.InvalidTokenError):
            provider.decode_token_insecure("bad.token")


def test_decode_token_insecure_empty_token_raises(provider):
    with pytest.raises(ValueError):
        provider.decode_token_insecure("")


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------

def test_decode_token_returns_user(provider):
    payload = {
        "sub": "user-123",
        "preferred_username": "tester",
        "email": "tester@example.com",
        "realm_access": {"roles": ["read"]},
        "scope": "openid profile",
    }
    mock_signing_key = MagicMock()
    mock_signing_key.key = "fake-key"
    provider.jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("fastapi_template.core.security.jwt.decode", return_value=payload):
        user = provider.decode_token("some.jwt.token")

    assert isinstance(user, User)
    assert user.sub == "user-123"


def test_decode_token_invalid_jwt_raises(provider):
    provider.jwk_client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("invalid")
    with pytest.raises(jwt.InvalidTokenError):
        provider.decode_token("bad.token")


def test_decode_token_empty_token_raises(provider):
    with pytest.raises(ValueError):
        provider.decode_token("")


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

_TOKEN_RESPONSE = {
    "access_token": "acc",
    "refresh_token": "ref",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_expires_in": 86400,
    "scope": "openid",
}


def test_authenticate_returns_token(provider):
    mock_response = MagicMock()
    mock_response.json.return_value = _TOKEN_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("fastapi_template.core.security.httpx.post", return_value=mock_response):
        token = provider.authenticate(username="user", password="pass")

    assert isinstance(token, Token)
    assert token.access_token == "acc"


def test_authenticate_empty_username_raises(provider):
    with pytest.raises(ValueError):
        provider.authenticate(username="", password="pass")


def test_authenticate_empty_password_raises(provider):
    with pytest.raises(ValueError):
        provider.authenticate(username="user", password="")


def test_authenticate_http_error_propagates(provider):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=MagicMock()
    )
    with patch("fastapi_template.core.security.httpx.post", return_value=mock_response):
        with pytest.raises(httpx.HTTPStatusError):
            provider.authenticate(username="user", password="wrong")


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------

def test_refresh_access_token_returns_token(provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {**_TOKEN_RESPONSE, "access_token": "new-acc"}
    mock_response.raise_for_status = MagicMock()

    with patch("fastapi_template.core.security.httpx.post", return_value=mock_response):
        token = provider.refresh_access_token("old-refresh-token")

    assert isinstance(token, Token)
    assert token.access_token == "new-acc"


def test_refresh_access_token_empty_raises(provider):
    with pytest.raises(ValueError):
        provider.refresh_access_token("")


# ---------------------------------------------------------------------------
# dummy_authenticate
# ---------------------------------------------------------------------------

def test_dummy_authenticate_returns_dev_token(provider):
    token = provider.dummy_authenticate(username="user", password="pass")
    assert isinstance(token, Token)
    assert token.access_token == "dev-access-token"


def test_dummy_authenticate_empty_username_raises(provider):
    with pytest.raises(ValueError):
        provider.dummy_authenticate(username="", password="pass")
