from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from django.utils import timezone

from cart.models import Quote
from notifications import services as svc
from notifications.models import Notification, NotificationConsumption
from orders.models import Event, Order


pytestmark = pytest.mark.django_db(transaction=True)


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


def require_mysql():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")


def test_duplicate_consumption_has_one_notice():
    require_mysql()
    user = User.objects.create_user("notification_race")
    quote = Quote.objects.create(
        user=user, snapshot={}, expires_at=timezone.now() + timedelta(minutes=5)
    )
    order = Order.objects.create(
        user=user,
        quote=quote,
        intent_id=uuid4(),
        address_snapshot={},
        goods_amount=0,
        freight_amount=0,
        discount_amount=0,
        payable_amount=0,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    event = Event.objects.create(order=order, kind="order.paid", actor=user)
    results = race([lambda: svc.deliver_order_event(event.pk)] * 2)
    assert sorted(results) == [False, True]
    assert Notification.objects.filter(event_id=event.event_id).count() == 1
    assert NotificationConsumption.objects.filter(event_id=event.event_id).count() == 1


def test_read_all_racing_new_notice_keeps_it_unread():
    require_mysql()
    user = User.objects.create_user("watermark_race")
    original = svc.create_notice(
        user, uuid4(), "order.paid", "order", "order", str(uuid4()), {"order_no": "A"}
    )
    token = svc.watermark(user, "")

    def add_notice():
        return svc.create_notice(
            user,
            uuid4(),
            "order.shipped",
            "order",
            "order",
            str(uuid4()),
            {"order_no": "B"},
        )

    created, marked = race(
        [add_notice, lambda: svc.mark_read(user, {"watermark": token})]
    )
    original.refresh_from_db()
    created.refresh_from_db()
    assert original.read_at is not None
    assert created.read_at is None
    assert created.recipient_seq > original.recipient_seq
    assert marked["total"] in (0, 1)
    assert svc.unread(user)["total"] == 1
