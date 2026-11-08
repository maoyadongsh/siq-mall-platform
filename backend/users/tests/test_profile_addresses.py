import pytest

from accounts.tests.conftest import csrf_post, register_user
from users.models import Address

from .conftest import address_payload, auth_headers, create_address

pytestmark = pytest.mark.django_db


def test_profile_allows_only_nickname_update(client):
    login = register_user(client)
    response = client.patch(
        "/api/v1/users/me/",
        {"nickname": "新昵称"},
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 200
    assert response.json()["data"]["nickname"] == "新昵称"

    for field in ("roles", "is_staff", "phone_verified_at"):
        response = client.patch(
            "/api/v1/users/me/",
            {field: "invalid"},
            format="json",
            **auth_headers(login),
        )
        assert response.status_code == 400


def test_first_address_defaults_and_ids_are_strings(client):
    login = register_user(client)
    first = create_address(client, login)
    second = create_address(client, login)
    assert first["is_default"] is True
    assert second["is_default"] is False
    assert isinstance(first["id"], str)

    response = client.get("/api/v1/users/me/addresses/", **auth_headers(login))
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_default_switch_is_atomic_and_idempotent(client):
    login = register_user(client)
    first = create_address(client, login)
    second = create_address(client, login)
    response = client.post(
        f"/api/v1/users/me/addresses/{second['id']}/default/",
        {},
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_default"] is True
    version = response.json()["data"]["version"]

    repeated = client.post(
        f"/api/v1/users/me/addresses/{second['id']}/default/",
        {},
        format="json",
        **auth_headers(login),
    )
    assert repeated.json()["data"]["version"] == version
    assert Address.objects.filter(user__username="buyer", is_default=True).count() == 1
    assert Address.objects.get(pk=first["id"]).is_default is False


def test_update_rejects_stale_version_and_increments_version(client):
    login = register_user(client)
    address = create_address(client, login)
    response = client.patch(
        f"/api/v1/users/me/addresses/{address['id']}/",
        address_payload(expected_version=2),
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 409
    assert response.json()["code"] == 10008

    response = client.patch(
        f"/api/v1/users/me/addresses/{address['id']}/",
        address_payload(detail="更新后的地址", expected_version=1),
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 200
    assert response.json()["data"]["detail"] == "更新后的地址"
    assert response.json()["data"]["version"] == 2


def test_delete_default_selects_latest_remaining_address(client):
    login = register_user(client)
    first = create_address(client, login)
    second = create_address(client, login)
    client.post(
        f"/api/v1/users/me/addresses/{second['id']}/default/",
        {},
        format="json",
        **auth_headers(login),
    )
    current = Address.objects.get(pk=second["id"])
    response = client.delete(
        f"/api/v1/users/me/addresses/{second['id']}/",
        {"expected_version": current.version},
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 200
    assert Address.objects.get(pk=first["id"]).is_default is True


def test_address_limit_is_enforced(client):
    login = register_user(client)
    for _ in range(20):
        create_address(client, login)
    response = client.post(
        "/api/v1/users/me/addresses/",
        address_payload(),
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 409
    assert response.json()["code"] == 20007


def test_other_users_address_returns_404_for_read_update_and_delete(client):
    login = register_user(client)
    address = create_address(client, login)
    other = register_user(client, username="other")
    for method in ("patch", "delete"):
        response = getattr(client, method)(
            f"/api/v1/users/me/addresses/{address['id']}/",
            address_payload(expected_version=1),
            format="json",
            **auth_headers(other),
        )
        assert response.status_code == 404
    response = client.post(
        f"/api/v1/users/me/addresses/{address['id']}/default/",
        {},
        format="json",
        **auth_headers(other),
    )
    assert response.status_code == 404


def test_phone_bind_challenge_binds_verified_phone(client):
    login = register_user(client)
    token = login.json()["data"]["csrf_token"]
    access = login.json()["data"]["access"]
    challenge = csrf_post(
        client,
        "/api/v1/auth/verifications/",
        {"purpose": "phone_bind", "target": "13800000000"},
        token,
        access=access,
    )
    assert challenge.status_code == 201
    data = challenge.json()["data"]
    response = csrf_post(
        client,
        "/api/v1/users/me/phone/",
        {
            "challenge_id": data["challenge_id"],
            "code": data["demo_code"],
            "phone": "13800000000",
        },
        token,
        access=access,
    )
    assert response.status_code == 200
    assert response.json()["data"]["has_verified_phone"] is True


def test_phone_bind_rejects_other_users_challenge_without_consuming_it(client):
    owner = register_user(client)
    token = owner.json()["data"]["csrf_token"]
    challenge = csrf_post(
        client,
        "/api/v1/auth/verifications/",
        {"purpose": "phone_bind", "target": "13800000000"},
        token,
        access=owner.json()["data"]["access"],
    )
    data = challenge.json()["data"]
    other = register_user(client, username="other")
    response = csrf_post(
        client,
        "/api/v1/users/me/phone/",
        {
            "challenge_id": data["challenge_id"],
            "code": data["demo_code"],
            "phone": "13800000000",
        },
        other.json()["data"]["csrf_token"],
        access=other.json()["data"]["access"],
    )
    assert response.status_code == 403

    response = csrf_post(
        client,
        "/api/v1/users/me/phone/",
        {
            "challenge_id": data["challenge_id"],
            "code": data["demo_code"],
            "phone": "13800000000",
        },
        token,
        access=owner.json()["data"]["access"],
    )
    assert response.status_code == 200


def test_address_rejects_invalid_region_and_unknown_fields(client):
    login = register_user(client)
    response = client.post(
        "/api/v1/users/me/addresses/",
        address_payload(region_code="invalid", role="admin"),
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 400
