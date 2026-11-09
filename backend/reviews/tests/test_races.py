from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from django.db import connection, connections
from common.exceptions import BusinessError
from reviews.models import Review, ReviewAction
from reviews.services import write
from .test_reviews import purchase, moderator

pytestmark = pytest.mark.django_db(transaction=True)


def race(commands):
    gate = Barrier(len(commands))

    def work(fn):
        try:
            gate.wait(timeout=15)
            return fn()
        except BusinessError as exc:
            return exc.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(commands)) as pool:
        return list(pool.map(work, commands))


def test_duplicate_submission_and_competing_moderators():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB row locks")
    client, buyer, sku, order, item = purchase()
    order.status = "completed"
    order.save(update_fields=["status"])
    payload = {"order_item_id": int(item), "rating": 2, "content": "真实低分评价"}
    key = uuid4()
    submitted = race([lambda: write(buyer, "submit", key, None, payload)] * 2)
    assert (
        submitted[0] == submitted[1]
        and Review.objects.count() == 1
        and ReviewAction.objects.count() == 1
    )
    rid = int(submitted[0]["id"])
    _, first = moderator("first_mod")
    _, second = moderator("second_mod")

    def decide(user, action):
        return write(
            user,
            "moderate",
            uuid4(),
            rid,
            {"expected_version": 1, "action": action, "reason": "人工复核"},
        )

    results = race([lambda: decide(first, "approve"), lambda: decide(second, "reject")])
    assert (
        results.count(10008) == 1
        and ReviewAction.objects.count() == 2
        and Review.objects.get().version == 2
    )

    from orders.tests.test_orders import create, quote
    from orders.models import Order

    another = create(client, quote(client, sku, buyer.addresses.first()))
    Order.objects.filter(order_no=another["order_no"]).update(status="completed")
    second_payload = {
        **payload,
        "order_item_id": int(another["items"][0]["order_item_id"]),
    }
    fresh_keys = race(
        [lambda: write(buyer, "submit", uuid4(), None, second_payload)] * 2
    )
    assert fresh_keys.count(70002) == 1 and Review.objects.count() == 2
