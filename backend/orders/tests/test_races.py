from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from django.utils import timezone
from cart.services import quote
from catalog.models import Category, Product, Sku
from common.exceptions import BusinessError
from users.models import Address
from orders import services
from orders.models import Order, Settlement, StockMovement

pytestmark = pytest.mark.django_db(transaction=True)


def resources():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")
    product = Product.objects.create(
        category=Category.objects.create(name="茶具"), title="杯", status="on_sale"
    )
    return Sku.objects.create(
        product=product, label="白", price="99.00", available_stock=10
    )


def candidate(i, sku):
    user = User.objects.create_user("order" + str(i))
    a = Address.objects.create(
        user=user,
        recipient="测试",
        phone="13800000000",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        region_code="330106",
        detail="测试",
    )
    q = quote(user, {"address_id": a.pk, "items": [{"sku_id": sku.pk, "quantity": 1}]})
    from uuid import UUID

    return user, {"intent_id": uuid4(), "quote_id": UUID(q["quote_id"])}, uuid4()


def race(functions):
    gate = Barrier(len(functions))

    def worker(fn):
        try:
            gate.wait(timeout=30)
            return fn()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(worker, functions))


def submit(entry):
    u, d, k = entry
    try:
        return services.execute(u, "order.create", k, d, lambda: services.place(u, d))[
            "order_no"
        ]
    except BusinessError as exc:
        assert exc.code == 30002
        return None


def test_fifty_buyers_ten_units():
    sku = resources()
    buyers = [candidate(i, sku) for i in range(50)]
    results = race([lambda e=e: submit(e) for e in buyers])
    assert results.count(None) == 40
    assert len(set(results) - {None}) == Order.objects.count() == 10
    sku.refresh_from_db()
    assert (sku.available_stock, sku.reserved_stock) == (0, 10)
    assert StockMovement.objects.count() == 10


def test_duplicate_submission_and_payment_timeout_compete():
    sku = resources()
    entry = candidate(0, sku)
    user = entry[0]
    numbers = race([lambda: submit(entry)] * 2)
    assert numbers[0] == numbers[1] and Order.objects.count() == 1
    order = Order.objects.get()
    d = {"order_no": order.order_no}
    payment = services.execute(
        user, "payment.create", uuid4(), d, lambda: services.init_payment(user, d)
    )
    due = timezone.now() + timedelta(seconds=3)
    Order.objects.filter(pk=order.pk).update(expires_at=due)
    # Each worker observes its side of the deadline; both contend for the same real row lock.
    from threading import local

    local_clock = local()

    def fake_now():
        return getattr(local_clock, "now", due)

    def pay():
        local_clock.now = due - timedelta(microseconds=1)
        try:
            services.execute(
                user,
                "payment.simulate",
                uuid4(),
                {},
                lambda: services.simulate(
                    user, payment["pay_no"], {"outcome": "success"}
                ),
            )
        except BusinessError as exc:
            assert exc.code == 40003

    def expire():
        local_clock.now = due + timedelta(microseconds=1)
        services.expire_one(order.pk)

    with patch("orders.services.timezone.now", fake_now):
        race([pay, expire])
    sku.refresh_from_db()
    order.refresh_from_db()
    assert sku.reserved_stock == 0 and StockMovement.objects.count() == 2
    assert (order.status, sku.available_stock, Settlement.objects.count()) in [
        ("paid", 9, 1),
        ("canceled", 10, 0),
    ]
