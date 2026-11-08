from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from catalog.models import Category, Product, Sku, StockAdjustment, CatalogEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_shop():
    user = User.objects.create_user("operator")
    user.groups.add(Group.objects.get(name="catalog_operator"))
    product = Product.objects.create(
        title="灯", category=Category.objects.create(name="灯具")
    )
    sku = Sku.objects.create(
        product=product, label="白", price="49.99", available_stock=3
    )
    client = APIClient()
    client.force_authenticate(user)
    return client, product, sku


def test_inventory_replay_conflict_and_audit(setup_shop):
    client, product, sku = setup_shop
    url = f"/api/v1/ops/skus/{sku.pk}/stock-adjustments/"
    key = {"HTTP_IDEMPOTENCY_KEY": str(uuid4())}
    data = {"expected_version": 1, "delta": -2, "reason": "盘点"}
    assert client.post(url, data, format="json").status_code == 400
    first = client.post(url, data, format="json", **key)
    assert first.status_code == 201
    assert (first.data["data"]["before"], first.data["data"]["after"]) == (3, 1)
    assert (
        client.post(url, data, format="json", **key).data["data"] == first.data["data"]
    )
    assert (
        client.post(url, {**data, "delta": 1}, format="json", **key).status_code == 409
    )
    assert (
        client.post(
            url,
            {**data, "expected_version": 2},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        ).status_code
        == 409
    )
    assert client.get(url).data["data"]["count"] == 1
    sku.refresh_from_db()
    assert (sku.version, sku.available_stock) == (2, 1)
    client.force_authenticate(User.objects.create_user("buyer"))
    assert client.get(url).status_code == 403
    assert client.post(url, data, format="json", **key).status_code == 403
    assert StockAdjustment.objects.count() == 1


def test_variant_edit_rejects_stock_overwrite_and_stale_writes(setup_shop):
    client, product, sku = setup_shop
    url = f"/api/v1/ops/skus/{sku.pk}/"
    data = {"expected_version": 1, "reason": "采购更新", "price": "39.99"}
    assert (
        client.patch(url, {**data, "available_stock": 25}, format="json").status_code
        == 400
    )
    Sku.objects.create(product=product, label="绿", price="39.99", available_stock=1)
    assert client.patch(url, {**data, "label": "绿"}, format="json").status_code == 400
    assert client.patch(url, data, format="json").status_code == 200
    assert client.patch(url, data, format="json").status_code == 409
    event = CatalogEvent.objects.get(action="sku_edit")
    assert event.snapshot["before"]["price"] == "49.99"
    assert event.snapshot["after"]["price"] == "39.99"


def test_upload_verifies_content_and_attaches_cover(setup_shop, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    client, product, _ = setup_shop
    url = "/api/v1/ops/media/"

    def send(payload):
        return client.post(
            url,
            {
                "file": SimpleUploadedFile(
                    "photo.png", payload, content_type="image/png"
                )
            },
            format="multipart",
        )

    assert send(b"<svg></svg>").status_code == 400
    assert send(b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    image = BytesIO()
    Image.new("RGB", (100, 50), "green").save(image, "PNG")
    result = send(image.getvalue())
    assert result.status_code == 201
    media = result.data["data"]
    assert media["url"].endswith(".webp")
    with Image.open(next(tmp_path.rglob("*.webp"))) as converted:
        assert converted.format == "WEBP" and converted.size == (100, 50)
    edit = f"/api/v1/ops/products/{product.pk}/"
    payload = {"expected_version": 1, "cover_id": media["asset_id"]}
    assert (
        client.patch(edit, payload, format="json").data["data"]["cover_url"]
        == media["url"]
    )
    assert client.patch(edit, payload, format="json").status_code == 409
