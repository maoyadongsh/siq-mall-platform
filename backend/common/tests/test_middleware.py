import re

import pytest


@pytest.mark.django_db
def test_request_id_is_echoed(client):
    response = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="abc1234567890def")
    assert response["X-Request-Id"] == "abc1234567890def"
    assert response.json()["request_id"] == "abc1234567890def"


@pytest.mark.django_db
def test_request_id_is_generated_when_absent_or_illegal(client):
    illegal = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="bad id!!")
    generated = illegal["X-Request-Id"]

    assert re.fullmatch(r"[0-9a-f]{16}", generated)
    assert illegal.json()["request_id"] == generated
