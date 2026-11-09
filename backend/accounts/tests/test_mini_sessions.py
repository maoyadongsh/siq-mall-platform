import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.models import AuthSession
from accounts.services import create_session


pytestmark = pytest.mark.django_db


def test_mini_login_refresh_logout_and_web_protocol_separation():
    User.objects.create_user("mini_buyer", password="safe-pass-123")
    client = APIClient()
    response = client.post(
        "/api/v1/auth/mini/login/",
        {"identifier": "mini_buyer", "password": "safe-pass-123"},
        format="json",
    )
    assert response.status_code == 200, response.content
    data = response.data["data"]
    assert data["refresh"] and data["access"]
    session = AuthSession.objects.get(session_id=data["session_id"])
    assert session.client_kind == AuthSession.ClientKind.MINI
    assert "mall_refresh" not in response.cookies
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
    assert client.get("/api/v1/users/me/").status_code == 200
    client.credentials()

    rotated = client.post(
        "/api/v1/auth/mini/refresh/", {"refresh": data["refresh"]}, format="json"
    )
    assert rotated.status_code == 200, rotated.content
    new_data = rotated.data["data"]
    assert new_data["refresh"] != data["refresh"]
    assert (
        client.post(
            "/api/v1/auth/mini/refresh/", {"refresh": data["refresh"]}, format="json"
        ).status_code
        == 401
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_data['access']}")
    assert (
        client.post("/api/v1/auth/mini/logout/", {}, format="json").status_code == 200
    )
    assert (
        client.post(
            "/api/v1/auth/mini/refresh/",
            {"refresh": new_data["refresh"]},
            format="json",
        ).status_code
        == 401
    )


def test_web_and_mini_refresh_tokens_cannot_cross_protocols():
    user = User.objects.create_user("cross_protocol")
    _, web_refresh, _ = create_session(user)
    response = APIClient().post(
        "/api/v1/auth/mini/refresh/", {"refresh": str(web_refresh)}, format="json"
    )
    assert response.status_code == 401
    _, mini_refresh, _ = create_session(user, AuthSession.ClientKind.MINI)
    web = APIClient()
    response = web.post(
        "/api/v1/auth/web/refresh/",
        HTTP_COOKIE=f"mall_refresh={mini_refresh}; mall_csrf=invalid",
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code in (401, 403)
