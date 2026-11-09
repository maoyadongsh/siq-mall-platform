from decimal import Decimal
from uuid import uuid4
from datetime import timedelta
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from catalog.models import Category, Product, Sku
from users.models import Address
from cart.models import Cart, CartItem, Quote

pytestmark = pytest.mark.django_db
ITEMS = "/api/v1/carts/items/"
MERGE = "/api/v1/carts/merge/"
QUOTE = "/api/v1/checkout/quote/"


@pytest.fixture
def shopper():
    user = User.objects.create_user("cart_buyer")
    client = APIClient()
    client.force_authenticate(user)
    product = Product.objects.create(
        category=Category.objects.create(name="器皿"),
        title="茶杯",
        status=Product.Status.ON_SALE,
    )
    sku = Sku.objects.create(
        product=product, label="白", price="128.99", available_stock=150
    )
    address = Address.objects.create(
        user=user,
        recipient="买家",
        phone="13800000000",
        region_code="330106",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="样例",
    )
    return client, user, sku, address


def post(client, url, body, key=None):
    return client.post(
        url, body, format="json", HTTP_IDEMPOTENCY_KEY=str(key or uuid4())
    )


def test_add_replay_limit_and_patch_isolation(shopper):
    client, user, sku, _ = shopper
    data = {"sku_id": str(sku.pk), "quantity": 99}
    key = uuid4()
    assert APIClient().get(ITEMS).status_code == 401
    first = post(client, ITEMS, data, key)
    assert first.status_code == 201
    assert post(client, ITEMS, data, key).data["data"] == first.data["data"]
    assert post(client, ITEMS, {**data, "quantity": 1}, key).status_code == 409
    assert post(client, ITEMS, {**data, "quantity": 1}).status_code == 409
    assert post(client, ITEMS, {**data, "quantity": 100}).status_code == 400
    item = first.data["data"]
    url = ITEMS + item["id"] + "/"
    change = {"quantity": 1, "selected": False, "expected_version": 1}
    assert client.patch(url, change, format="json").status_code == 200
    assert client.patch(url, change, format="json").status_code == 409
    client.force_authenticate(User.objects.create_user("other"))
    assert client.get(ITEMS).data["data"]["items"] == []
    assert client.delete(url, {"expected_version": 2}, format="json").status_code == 404
    client.force_authenticate(user)
    assert client.delete(url, {"expected_version": 2}, format="json").status_code == 200
    assert CartItem.objects.count() == 0


def test_merge_rejections_remain_explicit_and_replay_safe(shopper):
    client, _, sku, _ = shopper
    sold = Sku.objects.create(
        product=sku.product, label="无货", price=1, available_stock=0
    )
    body = {
        "items": [
            {"sku_id": sku.pk, "quantity": 2},
            {"sku_id": sold.pk, "quantity": 1},
            {"sku_id": 999999, "quantity": 1},
        ]
    }
    key = uuid4()
    first = post(client, MERGE, body, key).data["data"]
    assert first["requires_confirmation"]
    assert [(x["sku_id"], x["quantity"]) for x in first["adjustments"]] == [
        (str(sold.pk), 1),
        ("999999", 1),
    ]
    assert post(client, MERGE, body, key).data["data"] == first
    assert CartItem.objects.get().quantity == 2
    sku.product.status = "off_sale"
    sku.product.save()
    listing = client.get(ITEMS).data["data"]["items"][0]
    assert listing["available"] is False
    assert (
        client.patch(
            ITEMS + listing["id"] + "/",
            {"selected": False, "expected_version": 1},
            format="json",
        ).status_code
        == 200
    )


def test_fifty_distinct_limit(shopper):
    client, user, sku, _ = shopper
    cart = Cart.objects.create(user=user)
    variants = Sku.objects.bulk_create(
        [
            Sku(product=sku.product, label=str(i), price=1, available_stock=2)
            for i in range(50)
        ]
    )
    CartItem.objects.bulk_create(
        [CartItem(cart=cart, sku=v, quantity=1) for v in variants]
    )
    result = post(client, MERGE, {"items": [{"sku_id": sku.pk, "quantity": 1}]})
    assert result.data["data"]["requires_confirmation"]
    assert cart.items.count() == 50


def test_quote_uses_server_prices_and_versions_without_reservation(shopper):
    client, user, sku, address = shopper
    data = {"items": [{"sku_id": sku.pk, "quantity": 1}], "address_id": address.pk}
    first = client.post(QUOTE, data, format="json")
    assert first.status_code == 200
    q = first.data["data"]
    assert (q["goods_amount"], q["freight_amount"], q["payable_amount"]) == (
        "128.99",
        "8.00",
        "136.99",
    )
    record = Quote.objects.get(pk=q["quote_id"], user=user)
    assert (
        timedelta(minutes=4, seconds=55)
        < record.expires_at - timezone.now()
        <= timedelta(minutes=5)
    )
    assert record.snapshot["address_summary"]["version"] == address.version
    sku.price = Decimal("129.00")
    sku.save()
    new = client.post(QUOTE, data, format="json").data["data"]
    assert (new["freight_amount"], new["payable_amount"]) == ("0.00", "129.00")
    assert record.snapshot["goods_amount"] == "128.99"
    sku.refresh_from_db()
    assert sku.available_stock == 150
    for bad in (
        {**data, "payable_amount": "0.01"},
        {**data, "user_coupon_id": 1},
        {**data, "items": data["items"] * 2},
    ):
        assert client.post(QUOTE, bad, format="json").status_code == 400
    sku.available_stock = 0
    sku.save()
    assert client.post(QUOTE, data, format="json").status_code == 409
    client.force_authenticate(User.objects.create_user("outsider"))
    assert client.post(QUOTE, data, format="json").status_code == 404
