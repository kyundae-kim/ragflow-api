import pytest
from jwt import InvalidTokenError
from unittest.mock import MagicMock

from fastapi_template.core.config import ServiceSettings
from fastapi_template.core.exceptions import AuthError
from fastapi_template.core.security import User
from fastapi_template.dependencies.security import get_current_user, require_permissions


def _build_user(roles: set[str], scopes: set[str]) -> User:
    return User(
        sub="subject",
        preferred_username="tester",
        email="tester@example.com",
        name="Tester",
        roles=roles,
        scopes=scopes,
    )


def test_get_current_user_uses_decode_token_with_mock():
    expected = _build_user(roles={"read"}, scopes={"profile"})

    provider = MagicMock()
    provider.decode_token.return_value = expected

    user = get_current_user(
        token="access-token",
        provider=provider,
        settings=ServiceSettings(),
    )

    provider.decode_token.assert_called_once_with(token="access-token")
    assert user == expected


def test_get_current_user_invalid_token_raises_auth_error():
    provider = MagicMock()
    provider.decode_token.side_effect = InvalidTokenError("bad token")

    with pytest.raises(AuthError) as exc:
        get_current_user(
            token="access-token",
            provider=provider,
            settings=ServiceSettings(),
        )

    assert exc.value.status_code == 401
    assert exc.value.error == "invalid_token"
    assert exc.value.error_description == "Invalid authentication credentials"


def test_get_current_user_key_error_raises_auth_error():
    provider = MagicMock()
    provider.decode_token.side_effect = KeyError("sub")

    with pytest.raises(AuthError) as exc:
        get_current_user(
            token="access-token",
            provider=provider,
            settings=ServiceSettings(),
        )

    assert exc.value.status_code == 401
    assert exc.value.error == "invalid_token"
    assert exc.value.error_description == "Invalid authentication credentials"


def test_require_permissions_role_and_scope_success():
    checker = require_permissions(required_roles=("read",), required_scopes=("profile",))
    user = _build_user(roles={"read", "write"}, scopes={"profile", "email"})

    assert checker(current_user=user) == user


def test_require_permissions_role_and_scope_failure():
    checker = require_permissions(required_roles=("read", "delete"), required_scopes=("profile", "admin"))
    user = _build_user(roles={"read"}, scopes={"profile"})

    with pytest.raises(AuthError) as exc:
        checker(current_user=user)

    assert exc.value.status_code == 403
    assert exc.value.error == "insufficient_scope"
    assert "roles: delete" in exc.value.error_description
    assert "scopes: admin" in exc.value.error_description
