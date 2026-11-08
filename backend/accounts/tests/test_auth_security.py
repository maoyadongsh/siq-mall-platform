import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .conftest import PASSWORD, csrf_post, csrf_token, login_user, register_user

pytestmark = pytest.mark.django_db


def test_buyer_and_plain_staff_cannot_read_roles(client):
    buyer_login = register_user(client)
    response = client.get(
        "/api/v1/ops/roles/",
        HTTP_AUTHORIZATION=f"Bearer {buyer_login.json()['data']['access']}",
    )
    assert response.status_code == 403

    staff = get_user_model().objects.create_user(
        username="plain-staff", password=PASSWORD, is_staff=True
    )
    staff_login = login_user(client, "plain-staff")
    response = client.get(
        "/api/v1/ops/roles/",
        HTTP_AUTHORIZATION=f"Bearer {staff_login.json()['data']['access']}",
    )
    assert response.status_code == 403
    assert staff.is_staff


def test_role_admin_can_read_roles(client):
    admin = get_user_model().objects.create_user(
        username="role-admin", password=PASSWORD
    )
    admin.groups.add(Group.objects.get(name="access_admin"))
    login = login_user(client, "role-admin")
    response = client.get(
        "/api/v1/ops/roles/",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['data']['access']}",
    )
    assert response.status_code == 200
    assert any(item["username"] == "role-admin" for item in response.json()["data"])


def test_login_identifier_throttle_returns_retry_after(client):
    register_user(client)
    token = csrf_token(client)
    for _ in range(5):
        response = csrf_post(
            client,
            "/api/v1/auth/login/",
            {"identifier": "buyer", "password": "wrong-password"},
            token,
        )
        assert response.status_code == 401

    response = csrf_post(
        client,
        "/api/v1/auth/login/",
        {"identifier": "buyer", "password": "wrong-password"},
        token,
    )
    assert response.status_code == 429
    assert response.json()["code"] == 10005
    assert response["Retry-After"]


def test_legacy_json_refresh_does_not_accept_session_refresh(client):
    login = register_user(client)
    response = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": client.cookies["mall_refresh"].value},
        format="json",
    )
    assert response.status_code == 401
    assert login.status_code == 201
