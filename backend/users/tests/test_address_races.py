from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from common.exceptions import BusinessError
from users.models import Address
from users.services import create_address, make_default
from .conftest import address_payload

pytestmark = pytest.mark.django_db(transaction=True)


def race(operations):
    barrier = Barrier(len(operations))

    def worker(operation):
        try:
            barrier.wait(timeout=8)
            operation()
            return 200
        except BusinessError as exc:
            return exc.http_status
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(worker, operations))


def test_address_limit_and_default_on_independent_connections():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB row locks")
    buyer = User.objects.create_user("address_race")
    addresses = [create_address(buyer, address_payload()) for _ in range(19)]
    assert sorted(race([lambda: create_address(buyer, address_payload())] * 2)) == [
        200,
        409,
    ]
    assert Address.objects.filter(user=buyer).count() == 20
    assert race(
        [
            lambda: make_default(buyer, addresses[1].id),
            lambda: make_default(buyer, addresses[2].id),
        ]
    ) == [200, 200]
    assert Address.objects.filter(user=buyer, is_default=True).count() == 1
