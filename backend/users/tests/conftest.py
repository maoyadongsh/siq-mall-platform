import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.tests.conftest import register_user


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


def auth_headers(response):
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['data']['access']}"}


def address_payload(**overrides):
    data = {
        "recipient": "测试收件人",
        "phone": "13800000000",
        "province": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "region_code": "330106",
        "detail": "测试路1号",
        "is_default": False,
    }
    data.update(overrides)
    return data


def create_address(client, login, **overrides):
    response = client.post(
        "/api/v1/users/me/addresses/",
        address_payload(**overrides),
        format="json",
        **auth_headers(login),
    )
    assert response.status_code == 201
    return response.json()["data"]


__all__ = ["address_payload", "auth_headers", "create_address", "register_user"]
