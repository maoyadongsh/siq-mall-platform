from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from common.exceptions import BusinessError
from catalog.maintenance import adjust_stock
from catalog.models import Category, Product, Sku, StockAdjustment


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_request", [True, False])
def test_competing_adjustments(same_request):
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB row locks")
    a = User.objects.create_user("stock_ops")
    b = a if same_request else User.objects.create_user("stock_ops_2")
    product = Product.objects.create(
        title="测试", category=Category.objects.create(name="测试")
    )
    sku = Sku.objects.create(
        product=product, label="A", price="1.00", available_stock=1
    )
    key = uuid4()
    gate = Barrier(2)

    def worker(pair):
        user, op_key = pair
        try:
            gate.wait(timeout=8)
            return adjust_stock(
                user,
                sku.pk,
                op_key,
                {"expected_version": 1, "delta": -1, "reason": "盘点"},
            ).pk
        except BusinessError as exc:
            assert exc.http_status == 409
            return None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(worker, [(a, key), (b, key if same_request else uuid4())])
        )
    sku.refresh_from_db()
    assert sku.available_stock == 0
    assert StockAdjustment.objects.count() == 1
    if same_request:
        assert results[0] == results[1] and results[0] is not None
    else:
        assert results.count(None) == 1
