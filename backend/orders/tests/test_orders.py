from uuid import uuid4
from datetime import timedelta
import pytest
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from cart.models import Quote
from catalog.models import Category, Product, Sku
from users.models import Address
from orders.models import (
    Order,
    Payment,
    Settlement,
    StockMovement,
    Event,
    OrderActivity,
)

pytestmark = pytest.mark.django_db


def buyer_fixture():
    user = User.objects.create_user("order_buyer")
    product = Product.objects.create(
        category=Category.objects.create(name="茶具"), title="茶杯", status="on_sale"
    )
    sku = Sku.objects.create(
        product=product, label="白", price="99.00", available_stock=10
    )
    client = APIClient()
    client.force_authenticate(user)
    address = Address.objects.create(
        user=user,
        recipient="买家",
        phone="13800000000",
        region_code="330106",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="测试1号",
    )
    return client, user, sku, address


def quote(client, sku, address):
    data = {"items": [{"sku_id": sku.pk, "quantity": 1}], "address_id": address.pk}
    return client.post("/api/v1/checkout/quote/", data, format="json").data["data"][
        "quote_id"
    ]


def post(client, path, data, key=None):
    return client.post(
        "/api/v1/" + path, data, format="json", HTTP_IDEMPOTENCY_KEY=str(key or uuid4())
    )


def create(client, q):
    data = {"intent_id": str(uuid4()), "quote_id": q}
    r = post(client, "orders/", data)
    assert r.status_code == 201, r.content
    return r.data["data"]


def test_full_lifecycle_snapshots_replay_and_permissions(settings):
    client, user, sku, address = buyer_fixture()
    q = quote(client, sku, address)
    intent = str(uuid4())
    key = uuid4()
    data = {"quote_id": q, "intent_id": intent}
    r = post(client, "orders/", data, key)
    assert r.status_code == 201, r.content
    obj = r.data["data"]
    no = obj["order_no"]
    assert obj["payable_amount"] == "107.00"
    assert post(client, "orders/", data, key).data["data"] == obj
    assert (
        post(client, "orders/", {**data, "intent_id": str(uuid4())}, key).status_code
        == 409
    )
    assert post(client, "orders/", data).data["data"]["order_no"] == no
    assert (
        client.get(f"/api/v1/orders/by-intent/{intent}/").data["data"]["order_no"] == no
    )
    assert (
        client.get(f"/api/v1/operations/order.create/{key}/").data["data"][
            "resource_id"
        ]
        == no
    )
    sku.refresh_from_db()
    assert (sku.available_stock, sku.reserved_stock) == (9, 1)
    sku.price = "120.00"
    sku.save()
    address.detail = "已改"
    address.save()
    snap = client.get(f"/api/v1/orders/{no}/").data["data"]
    assert (
        snap["items"][0]["unit_price"] == "99.00"
        and snap["address_snapshot"]["detail"] == "测试1号"
    )
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    other = APIClient()
    staff = User.objects.create_user("other", is_staff=True)
    other.force_authenticate(staff)
    assert other.get(f"/api/v1/orders/{no}/").status_code == 404
    assert (
        post(other, f"payments/{pay}/simulate/", {"outcome": "success"}).status_code
        == 404
    )
    assert (
        post(
            other,
            f"ops/orders/{no}/ship/",
            {"carrier": "A", "tracking_no": "1", "expected_version": 1},
        ).status_code
        == 403
    )
    settings.DEMO_PAYMENT_ENABLED = False
    assert client.get(f"/api/v1/orders/{no}/").data["data"]["allowed_actions"] == [
        "cancel"
    ]
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "success"}).status_code
        == 403
    )
    settings.DEMO_PAYMENT_ENABLED = True
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "failed"}).data["data"][
            "status"
        ]
        == "failed"
    )
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    Payment.objects.filter(pay_no=pay).update(amount="0.01")
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "success"}).status_code
        == 409
    )
    Payment.objects.filter(pay_no=pay).update(amount="107.00")
    key2 = uuid4()
    for _ in range(2):
        assert (
            post(
                client, f"payments/{pay}/simulate/", {"outcome": "success"}, key2
            ).status_code
            == 200
        )
    sku.refresh_from_db()
    assert (sku.available_stock, sku.reserved_stock) == (9, 0)
    assert Settlement.objects.count() == 1 and StockMovement.objects.count() == 2
    from orders.services import expire_one

    assert not expire_one(Order.objects.get().pk)
    assert post(client, f"orders/{no}/cancel/", {"reason": "other"}).status_code == 409
    operator = User.objects.create_user("shipper")
    operator.groups.add(Group.objects.get(name="order_operator"))
    ops = APIClient()
    ops.force_authenticate(operator)
    assert (
        "address_snapshot"
        not in ops.get("/api/v1/ops/orders/").data["data"]["results"][0]
    )
    payload = {"carrier": "演示物流", "tracking_no": "DEMO001", "expected_version": 2}
    assert (
        post(
            ops, f"ops/orders/{no}/ship/", {**payload, "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        post(ops, f"ops/orders/{no}/ship/", payload).data["data"]["status"] == "shipped"
    )
    assert post(other, f"orders/{no}/receive/", {}).status_code == 404
    assert (
        post(client, f"orders/{no}/receive/", {}).data["data"]["status"] == "completed"
    )
    assert post(client, "orders/", data, key).data["data"] == obj
    assert Order.objects.count() == 1 and Event.objects.count() == 4
    assert not OrderActivity.objects.exists()
    for _ in range(2):
        call_command("process_order_events")
    assert OrderActivity.objects.count() == 4
    assert client.get("/api/v1/ops/order-activities/").status_code == 403
    feed = ops.get("/api/v1/ops/order-activities/").data["data"]
    assert len(feed) == 4 and feed[0]["type"] == "order.completed"


def test_invalid_quote_and_timeout_release():
    client, user, sku, address = buyer_fixture()
    q = quote(client, sku, address)
    sku.price = "98.00"
    sku.save()
    assert (
        post(client, "orders/", {"quote_id": q, "intent_id": str(uuid4())}).data["code"]
        == 40005
    )
    assert not Order.objects.exists() and not StockMovement.objects.exists()
    q = quote(client, sku, address)
    Quote.objects.filter(pk=q).update(expires_at=timezone.now())
    assert (
        post(client, "orders/", {"quote_id": q, "intent_id": str(uuid4())}).data["code"]
        == 40006
    )
    no = create(client, quote(client, sku, address))["order_no"]
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    Order.objects.filter(order_no=no).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "success"}).data["code"]
        == 40007
    )
    for _ in range(2):
        call_command("process_order_events")
    assert (
        post(client, f"orders/{no}/cancel/", {"reason": "other"}).data["data"]["status"]
        == "canceled"
    )
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "success"}).status_code
        == 409
    )
    sku.refresh_from_db()
    assert (sku.available_stock, sku.reserved_stock) == (10, 0)
    assert StockMovement.objects.filter(kind="release").count() == 1
    assert OrderActivity.objects.count() == 2


def test_checkout_rolls_back_all_items_on_failure(monkeypatch):
    from orders import services

    client, user, sku, address = buyer_fixture()
    other = Sku.objects.create(
        product=sku.product, label="绿", price="29.00", available_stock=2
    )
    q = client.post(
        "/api/v1/checkout/quote/",
        {
            "address_id": address.pk,
            "items": [
                {"sku_id": sku.pk, "quantity": 1},
                {"sku_id": other.pk, "quantity": 1},
            ],
        },
        format="json",
    ).data["data"]["quote_id"]
    real_move = services.move

    def fail_second(item, stock, kind):
        if item.sku_id == other.pk:
            raise RuntimeError("injected failure")
        return real_move(item, stock, kind)

    monkeypatch.setattr(services, "move", fail_second)
    response = post(client, "orders/", {"intent_id": str(uuid4()), "quote_id": q})
    assert response.status_code == 500
    sku.refresh_from_db()
    assert (sku.available_stock, sku.reserved_stock) == (10, 0)
    assert not Order.objects.exists() and not Event.objects.exists()
    assert (
        not StockMovement.objects.exists() and not services.Operation.objects.exists()
    )


def test_changed_address_and_outbox_retry(monkeypatch):
    from django.core.management.base import CommandError

    client, user, sku, address = buyer_fixture()
    q = quote(client, sku, address)
    address.version += 1
    address.detail = "新地址"
    address.save()
    assert (
        post(client, "orders/", {"quote_id": q, "intent_id": str(uuid4())}).data["code"]
        == 40005
    )
    no = create(client, quote(client, sku, address))["order_no"]
    post(client, "orders/" + no + "/cancel/", {"reason": "user_changed_mind"})
    real = OrderActivity.objects.get_or_create

    def crash_after_write(**kwargs):
        result = real(**kwargs)
        if kwargs["event"].kind == "order.created":
            raise RuntimeError("simulated worker interruption")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(OrderActivity.objects, "get_or_create", crash_after_write)
        with pytest.raises(CommandError):
            call_command("process_order_events")
    assert Event.objects.get(kind="order.created").delivered_at is None
    assert OrderActivity.objects.count() == 1
    call_command("process_order_events")
    call_command("process_order_events")
    assert OrderActivity.objects.count() == 2


def test_illegal_transitions_and_replay_after_shipment():
    from cart.models import Cart, CartItem

    client, user, sku, address = buyer_fixture()
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, sku=sku, selected=True, quantity=1)
    q = quote(client, sku, address)
    intent = str(uuid4())
    r = post(client, "orders/", {"quote_id": q, "intent_id": intent})
    no = r.data["data"]["order_no"]
    assert not cart.items.exists()
    assert (
        post(client, "orders/", {"quote_id": q, "intent_id": str(uuid4())}).data["code"]
        == 40004
    )
    assert (
        post(client, "orders/", {"quote_id": str(uuid4()), "intent_id": intent}).data[
            "code"
        ]
        == 10010
    )
    assert post(client, f"orders/{no}/receive/", {}).status_code == 409
    shipper = User.objects.create_superuser("fulfiller", password="test-only")
    ops = APIClient()
    ops.force_authenticate(shipper)
    shipment = {"carrier": "演示物流", "tracking_no": "DEMO", "expected_version": 1}
    assert post(ops, f"ops/orders/{no}/ship/", shipment).status_code == 409
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    simulate = f"payments/{pay}/simulate/"
    assert post(client, simulate, {"outcome": "success"}).status_code == 200
    assert post(client, simulate, {"outcome": "success"}).status_code == 200
    assert post(client, simulate, {"outcome": "failed"}).status_code == 409
    assert post(client, "payments/", {"order_no": no}).status_code == 409
    key = uuid4()
    for _ in range(2):
        assert (
            post(
                ops, f"ops/orders/{no}/ship/", {**shipment, "expected_version": 2}, key
            ).data["data"]["shipment"]["tracking_no"]
            == "DEMO"
        )
    for _ in range(2):
        assert post(client, f"orders/{no}/receive/", {}).status_code == 200


def test_deadlock_retry_uses_original_command_and_busy_header(monkeypatch):
    from django.db import OperationalError
    from orders import services

    client, user, sku, address = buyer_fixture()
    q = quote(client, sku, address)
    original = services.run_once
    keys = []

    def transient(*args):
        keys.append(args[2])
        if len(keys) == 1:
            raise OperationalError(1213, "lock victim")
        return original(*args)

    monkeypatch.setattr(services, "run_once", transient)
    no = create(client, q)["order_no"]
    assert keys[0] == keys[1]

    def blocked(*args):
        raise OperationalError(1205, "timeout")

    monkeypatch.setattr(services, "run_once", blocked)
    response = post(client, f"orders/{no}/cancel/", {"reason": "other"})
    assert response.data["code"] == 10009 and response["Retry-After"] == "1"
    assert Order.objects.get().status == "pending"
