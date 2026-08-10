import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from fastapi_template.schemas import TokenResponse, UserInfo


@pytest.fixture(scope="module")
def client():
    """TestClient backed by a real Keycloak; DB engine is mocked out."""
    from fastapi_template.factory import create_app

    mock_engine = MagicMock()

    def fake_setup_db_engine(app, config):
        app.state.db_engine = mock_engine

    with (
        patch("fastapi_template.factory.setup_db_engine", side_effect=fake_setup_db_engine),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="module")
def token(client):
    """Obtain a real access token from Keycloak once per test module."""
    response = client.post(
        "/token",
        data={"username": "test", "password": "test"},
    )
    assert response.status_code == 200, f"Failed to obtain token: {response.text}"
    return TokenResponse(**response.json()).access_token


# ---------------------------------------------------------------------------
# /token tests
# ---------------------------------------------------------------------------


def test_get_token(client):
    response = client.post(
        "/token",
        data={"username": "test", "password": "test"},
    )
    assert response.status_code == 200
    token_data = TokenResponse(**response.json())
    assert token_data.access_token
    assert token_data.token_type == "Bearer"


def test_get_token_invalid_password(client):
    response = client.post(
        "/token",
        data={"username": "test", "password": "wrong-password"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "invalid_grant"


def test_get_token_invalid_username(client):
    response = client.post(
        "/token",
        data={"username": "nonexistent-user", "password": "test"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "invalid_grant"


# ---------------------------------------------------------------------------
# /user tests
# ---------------------------------------------------------------------------


def test_get_user_info(client, token):
    response = client.get("/user", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    user = UserInfo(**response.json())
    assert user.sub


def test_get_user_info_no_token(client):
    response = client.get("/user")
    assert response.status_code == 401


def test_get_user_info_invalid_token(client):
    response = client.get(
        "/user", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "invalid_token"


def test_get_user_info_malformed_header(client):
    response = client.get("/user", headers={"Authorization": "NotBearer token"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /example role-gated endpoint tests
# ---------------------------------------------------------------------------


def test_example_read_with_token(client, token):
    """Result depends on whether the Keycloak user has the 'read' role."""
    response = client.get(
        "/example", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert response.json()["message"] == (
            "This is an example endpoint that requires 'read' role."
        )
    else:
        assert response.json()["error"] == "insufficient_scope"


def test_example_create_with_token(client, token):
    """Result depends on whether the Keycloak user has the 'create' role."""
    response = client.post(
        "/example", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code in (200, 403)


def test_example_delete_with_token(client, token):
    """Result depends on whether the Keycloak user has the 'delete' role."""
    response = client.delete(
        "/example", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code in (200, 403)


def test_example_read_no_token(client):
    response = client.get("/example")
    assert response.status_code == 401
