import socket
from django.core.cache import cache
from redis.exceptions import ConnectionError as RedisConnectionError
from uuid import uuid4, UUID
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from cart.services import quote
from common.exceptions import BusinessError
from orders import services
from orders.models import Order
from promotions.models import Template, Coupon
from promotions.services import command
from orders.tests.test_orders import buyer_fixture


pytestmark = pytest.mark.django_db(transaction=True)


def template(total):
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")
    now = timezone.now()
    return Template.objects.create(
        name="限量券",
        type="fixed",
        threshold_amount="1.00",
        reduction_amount="1.00",
        scope="all",
        total=total,
        start_at=now - timedelta(days=1),
        claim_start_at=now - timedelta(hours=1),
        end_at=now + timedelta(days=1),
        claim_end_at=now + timedelta(hours=1),
        status="active",
    )


def race(functions):
    gate = Barrier(len(functions))

    def worker(fn):
        try:
            gate.wait(timeout=45)
            return fn()
        except BusinessError as e:
            assert e.http_status == 409
            return None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(worker, functions))


def test_hundred_users_fifty_coupons():
    t = template(50)
    users = [User.objects.create_user(f"coupon{i}") for i in range(100)]
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        cache_url = f"redis://127.0.0.1:{endpoint.getsockname()[1]}/0"
        with override_settings(
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": cache_url,
                }
            }
        ):
            with pytest.raises(RedisConnectionError):
                cache.get("i07-acceptance")
            from rest_framework.test import APIClient

            api = APIClient()
            api.force_authenticate(users[0])
            assert (
                api.post(
                    f"/api/v1/coupons/{t.pk}/claim/",
                    {},
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=str(uuid4()),
                ).status_code
                == 503
            )
            result = race(
                [lambda u=u: command(u, t.pk, "claim", uuid4(), {}) for u in users]
            )
    t.refresh_from_db()
    assert result.count(None) == 50
    assert (
        len({r["id"] for r in result if r}) == t.issued == Coupon.objects.count() == 50
    )

    # Exercise the HTTP entry point with the rate limiter available as well.
    public_template = template(50)

    def send(user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user)
        response = client.post(
            f"/api/v1/coupons/{public_template.pk}/claim/",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        return response.status_code

    codes = race([lambda u=u: send(u) for u in users])
    assert codes.count(201) == 50 and codes.count(409) == 50
    public_template.refresh_from_db()
    assert (
        public_template.issued
        == Coupon.objects.filter(template=public_template).count()
        == 50
    )


def test_two_intents_contend_for_one_coupon():
    t = template(2)
    client, user, sku, address = buyer_fixture()
    c = command(user, t.pk, "claim", uuid4(), {})
    payload = {
        "items": [{"sku_id": sku.pk, "quantity": 1}],
        "address_id": address.pk,
        "user_coupon_id": c["id"],
    }
    bids = [
        {"intent_id": uuid4(), "quote_id": UUID(quote(user, payload)["quote_id"])}
        for _ in range(2)
    ]
    results = race(
        [
            lambda b=b: services.execute(
                user, "order.create", uuid4(), b, lambda: services.place(user, b)
            )
            for b in bids
        ]
    )
    sku.refresh_from_db()
    assert results.count(None) == 1 and Order.objects.count() == 1
    assert sku.available_stock == 9 and sku.reserved_stock == 1
    assert Coupon.objects.get(pk=c["id"]).status == "reserved"
