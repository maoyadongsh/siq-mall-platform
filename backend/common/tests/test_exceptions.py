import json

from common.exceptions import handler500


def test_unknown_route_returns_unified_404(client):
    response = client.get("/api/v1/not-exist/")
    body = response.json()

    assert response.status_code == 404
    assert body["code"] == 10004
    assert body["message"] == "资源不存在"


def test_method_not_allowed_returns_10007(client):
    response = client.post("/api/v1/health/")
    assert response.status_code == 405
    assert response.json()["code"] == 10007


def test_missing_field_returns_validation_error(client):
    response = client.post(
        "/api/v1/auth/refresh/", data={}, content_type="application/json"
    )
    body = response.json()

    assert response.status_code == 400
    assert body["code"] == 10001
    assert body["errors"][0]["field"] == "refresh"


def test_invalid_refresh_token_returns_20004(client):
    response = client.post(
        "/api/v1/auth/refresh/",
        data={"refresh": "not-a-token"},
        content_type="application/json",
    )
    body = response.json()

    assert response.status_code == 401
    assert body["code"] == 20004
    assert "refresh" in body["message"]


def test_handler500_hides_internal_detail():
    response = handler500(request=None)
    body = json.loads(response.content)

    assert response.status_code == 500
    assert body["code"] == 10006
    assert "服务内部错误" in body["message"]
