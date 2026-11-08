import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

PASSWORD = "Strong-pass-9384"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


def csrf_token(client):
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"]


def csrf_post(client, path, data, token, access=None):
    headers = {
        "HTTP_ORIGIN": "http://testserver",
        "HTTP_X_CSRF_TOKEN": token,
    }
    if access:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {access}"
    return client.post(path, data, format="json", **headers)


def register_user(client, username="buyer", password=PASSWORD):
    token = csrf_token(client)
    response = csrf_post(
        client,
        "/api/v1/auth/register/",
        {
            "username": username,
            "password": password,
            "accepted_terms_version": "demo-v1",
        },
        token,
    )
    assert response.status_code == 201
    return response


def login_user(client, username, password=PASSWORD):
    token = csrf_token(client)
    response = csrf_post(
        client,
        "/api/v1/auth/login/",
        {"identifier": username, "password": password},
        token,
    )
    assert response.status_code == 200
    return response
