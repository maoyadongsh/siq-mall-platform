from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from catalog.models import Product, Sku, Category
from cart.models import CartItem
from cart.services import add_items


@pytest.mark.django_db(transaction=True)
def test_parallel_first_merge_replays_same_result():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")
    user = User.objects.create_user("merge")
    p = Product.objects.create(
        title="商品", category=Category.objects.create(name="分类"), status="on_sale"
    )
    sku = Sku.objects.create(product=p, label="绿", price=10, available_stock=10)
    key = uuid4()
    gate = Barrier(2)

    def run():
        try:
            gate.wait(timeout=10)
            return add_items(user, "merge", key, [{"sku_id": sku.pk, "quantity": 3}])
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        assert futures[0].result() == futures[1].result()
    assert CartItem.objects.get().quantity == 3
