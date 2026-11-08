import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient
from catalog.models import CatalogEvent


@pytest.mark.django_db
def test_catalog_visibility_permission_and_version():
    buyer = User.objects.create_user("buyer")
    ops = User.objects.create_user("ops")
    ops.groups.add(Group.objects.get(name="catalog_operator"))
    client = APIClient()
    data = {
        "title": "茶杯",
        "category": "器具",
        "skus": [
            {"label": "白", "price": "99.00", "available_stock": 1},
            {"label": "绿", "price": "129.00", "available_stock": 0},
        ],
    }
    client.force_authenticate(buyer)
    assert client.post("/api/v1/ops/products/", data, format="json").status_code == 403
    client.force_authenticate(ops)
    created = client.post("/api/v1/ops/products/", data, format="json")
    assert created.status_code == 201, created.content
    pk = created.data["data"]["id"]
    public = f"/api/v1/products/{pk}/"
    ops_url = f"/api/v1/ops/products/{pk}/"
    assert client.get(public).status_code == 404
    assert client.post(ops_url + "publish/", {"expected_version": 1}).status_code == 200
    result = APIClient().get(public).data["data"]
    assert [(s["price"], s["available_stock"]) for s in result["skus"]] == [
        ("99.00", 1),
        ("129.00", 0),
    ]
    assert (
        client.post(ops_url + "unpublish/", {"expected_version": 1}).status_code == 409
    )
    assert (
        client.post(ops_url + "unpublish/", {"expected_version": 2}).status_code == 200
    )
    assert APIClient().get(public).status_code == 404
    assert CatalogEvent.objects.count() == 3
