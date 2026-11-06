from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import Throttled
from rest_framework.views import APIView

from common import health
from common.exceptions import api_exception_handler
from common.response import get_request_id


def test_concurrent_probes_use_independent_keys(monkeypatch):
    barrier = Barrier(2)
    values = {}

    def put(key, value, timeout):
        values[key] = value
        barrier.wait(timeout=5)

    monkeypatch.setattr(
        health,
        "cache",
        SimpleNamespace(set=put, get=values.get, delete=lambda key: None),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: health.check_cache(), range(2)))
    assert all(result.status == "ok" for result in results)
    assert len(values) == 2


def test_dependency_failure_does_not_return_connection_details(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("redis://secret-password@internal-host:6379")

    monkeypatch.setattr(health.cache, "set", fail)
    result = health.check_cache()
    assert result.status == "fail"
    assert result.detail == "RuntimeError"


def test_throttle_preserves_retry_after():
    response = api_exception_handler(Throttled(wait=17), {"view": APIView()})
    assert response.status_code == 429
    assert response["Retry-After"] == "17"


@pytest.mark.django_db
def test_request_context_is_cleared_after_response(client):
    response = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="isolated-request")
    assert response.json()["request_id"] == "isolated-request"
    assert get_request_id() == ""


@pytest.mark.django_db
def test_refresh_rotates_and_rejects_reuse(client, django_user_model):
    from rest_framework_simplejwt.tokens import RefreshToken

    user = django_user_model.objects.create_user(username="rotation-test")
    original = str(RefreshToken.for_user(user))
    response = client.post("/api/v1/auth/refresh/", {"refresh": original})
    assert response.status_code == 200
    assert response.json()["data"]["refresh"] != original
    assert (
        client.post("/api/v1/auth/refresh/", {"refresh": original}).status_code == 401
    )


def test_schema_describes_health_and_refresh():
    from drf_spectacular.generators import SchemaGenerator
    from common.urls import urlpatterns

    schema = SchemaGenerator(patterns=urlpatterns).get_schema(request=None, public=True)
    assert "503" in schema["paths"]["/health/"]["get"]["responses"]
    assert "requestBody" in schema["paths"]["/auth/refresh/"]["post"]
