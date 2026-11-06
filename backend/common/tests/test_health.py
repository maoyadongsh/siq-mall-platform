import pytest

from common.health import CheckResult


@pytest.mark.django_db
def test_health_returns_ok_when_dependencies_alive(client):
    response = client.get("/api/v1/health/")
    body = response.json()

    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"
    assert body["data"]["checks"]["database"]["status"] == "ok"
    assert body["data"]["checks"]["redis"]["status"] == "ok"
    assert body["data"]["version"]


@pytest.mark.django_db
def test_health_returns_503_when_cache_down(client, monkeypatch):
    monkeypatch.setattr(
        "common.health.check_cache",
        lambda: CheckResult("fail", 0.0, "connection refused"),
    )
    response = client.get("/api/v1/health/")
    body = response.json()

    assert response.status_code == 503
    assert body["data"]["status"] == "degraded"
    assert body["data"]["checks"]["redis"]["status"] == "fail"


@pytest.mark.django_db
def test_health_returns_503_when_database_down(client, monkeypatch):
    monkeypatch.setattr(
        "common.health.check_database",
        lambda: CheckResult("fail", 0.0, "can't connect"),
    )
    response = client.get("/api/v1/health/")
    assert response.status_code == 503
    assert response.json()["data"]["checks"]["database"]["status"] == "fail"
