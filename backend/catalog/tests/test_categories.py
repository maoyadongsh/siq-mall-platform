from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import CommandError, call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from catalog.models import Category, CategoryEvent, Product, Sku


pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def operator():
    user = User.objects.create_user("category_operator")
    user.groups.add(Group.objects.get(name="catalog_operator"))
    return client_for(user)


def create_category(client, name, parent=None):
    response = client.post(
        "/api/v1/ops/categories/",
        {"name": name, "parent_id": parent, "sort_order": 0, "enabled": True},
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.data["data"]


def product(category, title, price):
    row = Product.objects.create(
        category=category, title=title, status="on_sale", min_price=price
    )
    Sku.objects.create(product=row, label="标准", price=price, available_stock=5)
    return row


def test_category_tree_cycle_permissions_and_audit():
    client = operator()
    root = create_category(client, "茶具")
    child = create_category(client, "茶杯", int(root["id"]))
    assert child["version"] == 1
    tree = APIClient().get("/api/v1/categories/tree/").data["data"]
    assert tree[0]["children"][0]["name"] == "茶杯"
    assert CategoryEvent.objects.count() == 2
    cycle = client.patch(
        f"/api/v1/ops/categories/{root['id']}/",
        {
            "name": "茶具",
            "parent_id": int(child["id"]),
            "sort_order": 0,
            "enabled": True,
            "expected_version": 1,
        },
        format="json",
    )
    assert cycle.status_code == 400
    ordinary = client_for(User.objects.create_user("category_buyer", is_staff=True))
    assert (
        ordinary.post("/api/v1/ops/categories/", {}, format="json").status_code == 403
    )
    disabled = client.patch(
        f"/api/v1/ops/categories/{root['id']}/",
        {
            "name": "茶具",
            "parent_id": None,
            "sort_order": 0,
            "enabled": False,
            "expected_version": 1,
        },
        format="json",
    )
    assert disabled.status_code == 200
    assert APIClient().get("/api/v1/categories/tree/").data["data"] == []


def test_product_filters_sort_price_and_query_count():
    root = Category.objects.create(name=" root ")
    child = Category.objects.create(name="child", parent=root)
    other = Category.objects.create(name="other")
    cheap = product(child, "便宜茶杯", "49.00")
    product(child, "标准茶杯", "99.00")
    product(other, "其他商品", "129.00")
    client = APIClient()
    filtered = client.get(f"/api/v1/products/?category={root.pk}&sort=price_asc").data[
        "data"
    ]
    assert filtered["count"] == 2
    assert filtered["results"][0]["id"] == str(cheap.pk)
    assert (
        client.get(
            f"/api/v1/products/?category={other.pk}&min_price=100&max_price=130"
        ).data["data"]["count"]
        == 1
    )
    assert client.get("/api/v1/products/?min_price=100&max_price=10").status_code == 400
    assert client.get("/api/v1/products/?min_price=-1").status_code == 400
    assert client.get("/api/v1/products/?sort=random").status_code == 400

    category = Category.objects.create(name="scale")
    products = [
        Product(category=category, title=f"scale-{i}", status="on_sale")
        for i in range(1000)
    ]
    created = Product.objects.bulk_create(products)
    Sku.objects.bulk_create(
        [
            Sku(product=row, label="标准", price="10.00", available_stock=1)
            for row in created
        ],
        batch_size=1000,
    )
    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/v1/products/?page_size=100&sort=price_asc")
    assert response.status_code == 200
    assert response.data["data"]["count"] == 1003
    assert len(response.data["data"]["results"]) == 100
    assert len(queries) <= 4, [query["sql"] for query in queries]


def test_scale_seed_is_explicit_and_cannot_duplicate():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(CommandError):
            call_command("seed_catalog_scale", products=1)
    with patch.dict("os.environ", {"MALL_ALLOW_SCALE_SEED": "1"}):
        call_command("seed_catalog_scale", products=10, skus=2, prefix="test-scale")
        assert Product.objects.filter(title__startswith="test-scale-").count() == 10
        assert (
            Sku.objects.filter(product__title__startswith="test-scale-").count() == 20
        )
        with pytest.raises(CommandError):
            call_command("seed_catalog_scale", products=10, prefix="test-scale")


def test_min_price_is_maintained_on_create_and_sku_price_edit():
    from catalog.maintenance import edit_sku
    from catalog.services import create_draft

    actor = User.objects.create_user("price_editor")
    product_row = create_draft(
        actor,
        {
            "category": "价格分类",
            "title": "多规格商品",
            "description": "",
            "skus": [
                {"label": "A", "price": "99.00", "available_stock": 2},
                {"label": "B", "price": "49.00", "available_stock": 2},
            ],
        },
    )
    assert str(product_row.min_price) == "49.00"
    sku = product_row.skus.get(label="A")
    edit_sku(actor, sku.pk, {"expected_version": 1, "price": "29.00", "reason": "调价"})
    product_row.refresh_from_db()
    assert str(product_row.min_price) == "29.00"
    first_sku = product_row.skus.get(label="B")
    edit_sku(
        actor,
        first_sku.pk,
        {"expected_version": 1, "price": "19.00", "reason": "再次调价"},
    )
    product_row.refresh_from_db()
    assert str(product_row.min_price) == "19.00"
