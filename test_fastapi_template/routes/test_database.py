import pytest
from fastapi.testclient import TestClient

from fastapi_template.factory import create_app


class DummyEngine:
    def dispose(self):
        return None


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ENV", "dev")

    dummy = DummyEngine()

    def fake_setup_db_engine(app, config):
        app.state.db_engine = dummy

    monkeypatch.setattr("fastapi_template.factory.setup_db_engine", fake_setup_db_engine)

    with TestClient(create_app()) as client:
        yield client


def test_database_ping_ready(app, monkeypatch):
    monkeypatch.setattr("fastapi_template.routes.database.check_database_connection", lambda engine: True)

    response = app.get("/db/example/ping")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "ready"
    assert json_data["engine"] == "postgresql"
    assert json_data["auth_method"] in {"password", "trust"}


def test_database_ping_not_ready(app, monkeypatch):
    monkeypatch.setattr("fastapi_template.routes.database.check_database_connection", lambda engine: False)

    response = app.get("/db/example/ping")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not reachable"


def test_database_version(app, monkeypatch):
    monkeypatch.setattr(
        "fastapi_template.routes.database.get_database_version",
        lambda engine: "PostgreSQL 16.3",
    )

    response = app.get("/db/example/version")

    assert response.status_code == 200
    assert response.json() == {"version": "PostgreSQL 16.3"}
