import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import AuthSession, Profile
from common.constants import ErrorCode

from .conftest import PASSWORD, csrf_post, csrf_token, login_user, register_user

pytestmark = pytest.mark.django_db


def test_register_creates_buyer_profile_and_cookie_session(client):
    response = register_user(client)
    body = response.json()
    user = get_user_model().objects.get(username="buyer")

    assert body["code"] == 0
    assert body["data"]["user"]["roles"] == ["buyer"]
    assert user.profile.nickname == "buyer"
    assert user.profile.phone is None
    assert user.is_active
    refresh_cookie = response.cookies["mall_refresh"]
    assert refresh_cookie["httponly"]
    assert refresh_cookie["samesite"] == "Lax"
    assert "refresh" not in body["data"]
    access = AccessToken(body["data"]["access"])
    assert access["exp"] - access["iat"] == 15 * 60


def test_duplicate_username_returns_409(client):
    register_user(client)
    token = csrf_token(client)
    response = csrf_post(
        client,
        "/api/v1/auth/register/",
        {
            "username": "buyer",
            "password": PASSWORD,
            "accepted_terms_version": "demo-v1",
        },
        token,
    )
    assert response.status_code == 409
    assert response.json()["code"] == ErrorCode.ACCOUNT_EXISTS


def test_weak_password_returns_400_without_user(client):
    token = csrf_token(client)
    response = csrf_post(
        client,
        "/api/v1/auth/register/",
        {
            "username": "weakpassworduser",
            "password": "123456",
            "accepted_terms_version": "demo-v1",
        },
        token,
    )
    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.PASSWORD_TOO_WEAK
    assert not get_user_model().objects.filter(username="weakpassworduser").exists()


def test_login_error_does_not_reveal_account_existence(client):
    register_user(client)
    token = csrf_token(client)
    unknown = csrf_post(
        client,
        "/api/v1/auth/login/",
        {"identifier": "missing", "password": "bad-password"},
        token,
    )
    wrong = csrf_post(
        client,
        "/api/v1/auth/login/",
        {"identifier": "buyer", "password": "bad-password"},
        token,
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["message"] == wrong.json()["message"] == "账号或密码不正确"


def test_protected_me_requires_session_access(client):
    login = register_user(client)
    access = login.json()["data"]["access"]

    assert client.get("/api/v1/users/me/").status_code == 401
    response = client.get("/api/v1/users/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "buyer"


def test_refresh_rotation_reuse_and_logout_revoke_immediately(client):
    login = register_user(client)
    original_refresh = client.cookies["mall_refresh"].value
    original_access = login.json()["data"]["access"]
    original_csrf = login.json()["data"]["csrf_token"]

    rotated = csrf_post(client, "/api/v1/auth/web/refresh/", {}, original_csrf)
    assert rotated.status_code == 200
    new_refresh = client.cookies["mall_refresh"].value
    new_csrf = rotated.json()["data"]["csrf_token"]
    assert new_refresh != original_refresh

    client.cookies["mall_refresh"] = original_refresh
    reused = csrf_post(client, "/api/v1/auth/web/refresh/", {}, new_csrf)
    assert reused.status_code == 401

    client.cookies["mall_refresh"] = new_refresh
    logout = csrf_post(
        client,
        "/api/v1/auth/logout/",
        {"scope": "current"},
        new_csrf,
        access=rotated.json()["data"]["access"],
    )
    assert logout.status_code == 200
    assert (
        client.get(
            "/api/v1/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {original_access}",
        ).status_code
        == 401
    )
    revoked = csrf_post(client, "/api/v1/auth/web/refresh/", {}, new_csrf)
    assert revoked.status_code == 401


def test_password_change_revokes_all_existing_sessions(client):
    login = register_user(client)
    old_access = login.json()["data"]["access"]
    response = csrf_post(
        client,
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "New-strong-pass-7284"},
        login.json()["data"]["csrf_token"],
        access=old_access,
    )
    assert response.status_code == 200
    assert (
        AuthSession.objects.filter(
            user__username="buyer", revoked_at__isnull=True
        ).count()
        == 0
    )
    assert (
        client.get(
            "/api/v1/users/me/", HTTP_AUTHORIZATION=f"Bearer {old_access}"
        ).status_code
        == 401
    )
    login_user(client, "buyer", "New-strong-pass-7284")


def test_demo_password_reset_is_one_time_and_revokes_sessions(client):
    login = register_user(client)
    token = csrf_token(client)
    challenge = csrf_post(
        client,
        "/api/v1/auth/verifications/",
        {"purpose": "password_reset", "target": "buyer"},
        token,
    )
    assert challenge.status_code == 201
    data = challenge.json()["data"]
    assert data["delivery"] == "demo_only_no_sms"

    wrong = csrf_post(
        client,
        "/api/v1/auth/password/reset/",
        {
            "challenge_id": data["challenge_id"],
            "code": "000000",
            "new_password": "Reset-strong-pass-8274",
        },
        token,
    )
    assert wrong.status_code == 400

    reset = csrf_post(
        client,
        "/api/v1/auth/password/reset/",
        {
            "challenge_id": data["challenge_id"],
            "code": data["demo_code"],
            "new_password": "Reset-strong-pass-8274",
        },
        token,
    )
    assert reset.status_code == 200
    assert (
        client.get(
            "/api/v1/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {login.json()['data']['access']}",
        ).status_code
        == 401
    )
    new_login = login_user(client, "buyer", "Reset-strong-pass-8274")
    token = new_login.json()["data"]["csrf_token"]

    reused = csrf_post(
        client,
        "/api/v1/auth/password/reset/",
        {
            "challenge_id": data["challenge_id"],
            "code": data["demo_code"],
            "new_password": "Another-strong-pass-6274",
        },
        token,
    )
    assert reused.status_code == 400


def test_verification_is_unavailable_without_demo_channel(client, settings):
    settings.DEMO_VERIFICATION_ENABLED = False
    token = csrf_token(client)
    response = csrf_post(
        client,
        "/api/v1/auth/verifications/",
        {"purpose": "password_reset", "target": "buyer"},
        token,
    )
    assert response.status_code == 503
    assert response.json()["code"] == ErrorCode.VERIFICATION_UNAVAILABLE


def test_csrf_and_origin_are_required(client):
    register_user(client)
    response = client.post(
        "/api/v1/auth/login/",
        {"identifier": "buyer", "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 403

    token = csrf_token(client)
    response = client.post(
        "/api/v1/auth/login/",
        {"identifier": "buyer", "password": PASSWORD},
        format="json",
        HTTP_ORIGIN="https://attacker.invalid",
        HTTP_X_CSRF_TOKEN=token,
    )
    assert response.status_code == 403


def test_profile_phone_is_only_login_identifier_after_verification(client):
    user = get_user_model().objects.create_user(
        username="phone-user", password=PASSWORD
    )
    Profile.objects.create(user=user, phone="13800000000")
    token = csrf_token(client)
    unverified = csrf_post(
        client,
        "/api/v1/auth/login/",
        {"identifier": "13800000000", "password": PASSWORD},
        token,
    )
    assert unverified.status_code == 401

    user.profile.phone_verified_at = "2026-11-06T00:00:00Z"
    user.profile.save(update_fields=["phone_verified_at"])
    login_user(client, "13800000000")
