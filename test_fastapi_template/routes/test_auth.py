import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

from fastapi_template.schemas import UserInfo, TokenResponse
from fastapi_template.factory import create_app
from fastapi_template.dependencies.security import get_current_user
from fastapi_template.core.security import User
from fastapi_template.routes import auth as auth_routes

@pytest.fixture(scope="module")
def app():
    app_instance = create_app()
    
    def fake_get_current_user():
        return User(
            sub="test-user",
            preferred_username="test",
            email="test@example.com",
            name="test test",
            roles={"read", "write"},
            scopes={"profile", "email"},
        )
    
    app_instance.dependency_overrides[get_current_user] = fake_get_current_user
    with TestClient(app_instance) as client:
        yield client

def test_get_token(app, monkeypatch):
    mocked_authenticate = Mock(
        return_value=TokenResponse(
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            token_type="Bearer",
            expires_in=3600,
            refresh_expires_in=86400,
            scope="profile email",
        )
    )
    monkeypatch.setattr(auth_routes, "authenticate", mocked_authenticate)

    response = app.post("/token", data={"username": "test", "password": "test"})
    assert response.status_code == 200
    token = TokenResponse(**response.json())
    assert len(token.access_token) > 0
    assert len(token.refresh_token) > 0
    assert token.token_type == "Bearer"
    mocked_authenticate.assert_called_once()

@pytest.fixture(scope="module")
def token(app):
    return "test-access-token"

def test_user_info(app, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = app.get("/user", headers=headers)
    assert response.status_code == 200
    user_info = UserInfo(**response.json())
    assert user_info.name == "test test"

def test_example_create(app, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = app.post("/example", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"] == "insufficient_scope"

def test_example_read(app, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = app.get("/example", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "This is an example endpoint that requires 'read' role."

def test_example_delete(app, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = app.delete("/example", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"] == "insufficient_scope"
