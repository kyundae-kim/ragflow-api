import pytest
import httpx
from unittest.mock import MagicMock, patch

from fastapi_template.core.config import KeycloakConfig, AuthSettings
from fastapi_template.core.exceptions import AuthError
from fastapi_template.core.security import Token, User, KeycloakAuthProvider
from fastapi_template.services.security import (
    get_auth_provider,
    authenticate,
    refresh_token,
    decode_token,
)


# ---------------------------------------------------------------------------
# Shared fixture: real KeycloakAuthProvider with no live network calls
# ---------------------------------------------------------------------------

@pytest.fixture
def provider():
    with patch("fastapi_template.core.security.jwt.PyJWKClient"):
        return KeycloakAuthProvider(
            url="http://keycloak:8080/",
            realm="test",
            client_id="fastapi",
        )


def _make_token() -> Token:
    return Token(
        access_token="access",
        refresh_token="refresh",
        token_type="Bearer",
        expires_in=3600,
        refresh_expires_in=86400,
        scope="openid",
    )


def _make_user() -> User:
    return User(
        sub="user-123",
        preferred_username="tester",
        email="tester@example.com",
        name="Test User",
        roles={"read"},
        scopes={"openid"},
    )


# ---------------------------------------------------------------------------
# get_auth_provider
# ---------------------------------------------------------------------------

def test_get_auth_provider_returns_keycloak_instance():
    config = KeycloakConfig()
    with patch("fastapi_template.core.security.jwt.PyJWKClient"):
        provider = get_auth_provider(config=config)
    assert isinstance(provider, KeycloakAuthProvider)


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

def test_authenticate_returns_token(provider):
    provider.authenticate = MagicMock(return_value=_make_token())

    token = authenticate(provider=provider, username="user", password="pass")

    provider.authenticate.assert_called_once_with(username="user", password="pass")
    assert isinstance(token, Token)
    assert token.access_token == "access"


def test_authenticate_invalid_credentials_raises_auth_error(provider):
    provider.authenticate = MagicMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
    )

    with pytest.raises(AuthError) as exc:
        authenticate(provider=provider, username="user", password="wrong")

    assert exc.value.status_code == 401
    assert exc.value.error == "invalid_grant"


def test_authenticate_timeout_raises_auth_error(provider):
    provider.authenticate = MagicMock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(AuthError) as exc:
        authenticate(provider=provider, username="user", password="pass")

    assert exc.value.status_code == 504
    assert exc.value.error == "temporarily_unavailable"


def test_authenticate_request_error_raises_auth_error(provider):
    provider.authenticate = MagicMock(side_effect=httpx.RequestError("network error"))

    with pytest.raises(AuthError) as exc:
        authenticate(provider=provider, username="user", password="pass")

    assert exc.value.status_code == 502
    assert exc.value.error == "server_error"


def test_authenticate_empty_username_raises_value_error(provider):
    with pytest.raises(ValueError):
        authenticate(provider=provider, username="", password="pass")


def test_authenticate_empty_password_raises_value_error(provider):
    with pytest.raises(ValueError):
        authenticate(provider=provider, username="user", password="")


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------

def test_refresh_token_returns_token(provider):
    provider.refresh_access_token = MagicMock(return_value=_make_token())

    new_token = refresh_token(provider=provider, token="old-refresh-token")

    provider.refresh_access_token.assert_called_once_with(token="old-refresh-token")
    assert isinstance(new_token, Token)


def test_refresh_token_http_error_raises_auth_error(provider):
    provider.refresh_access_token = MagicMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
    )

    with pytest.raises(AuthError) as exc:
        refresh_token(provider=provider, token="expired-token")

    assert exc.value.status_code == 401
    assert exc.value.error == "invalid_grant"


def test_refresh_token_timeout_raises_auth_error(provider):
    provider.refresh_access_token = MagicMock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(AuthError) as exc:
        refresh_token(provider=provider, token="some-token")

    assert exc.value.status_code == 504
    assert exc.value.error == "temporarily_unavailable"


def test_refresh_token_empty_raises_value_error(provider):
    with pytest.raises(ValueError):
        refresh_token(provider=provider, token="")


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------

def test_decode_token_verify_jwt_true_calls_decode_token(provider):
    provider.decode_token = MagicMock(return_value=_make_user())
    config = AuthSettings(verify_jwt=True)

    user = decode_token(provider=provider, token="some.jwt.token", config=config)

    provider.decode_token.assert_called_once_with(token="some.jwt.token")
    assert isinstance(user, User)


def test_decode_token_verify_jwt_false_calls_insecure(provider):
    provider.decode_token_insecure = MagicMock(return_value=_make_user())
    config = AuthSettings(verify_jwt=False)

    user = decode_token(provider=provider, token="some.jwt.token", config=config)

    provider.decode_token_insecure.assert_called_once_with(token="some.jwt.token")
    assert isinstance(user, User)


def test_decode_token_empty_token_raises_value_error(provider):
    config = AuthSettings()
    with pytest.raises(ValueError):
        decode_token(provider=provider, token="", config=config)
