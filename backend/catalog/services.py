from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from common.constants import ErrorCode
from common.exceptions import BusinessError
from .models import CatalogEvent, Category, Product, Sku
from .serializers import ProductOutput


@transaction.atomic
def create_draft(actor, data):
    category, _ = Category.objects.get_or_create(name=data["category"])
    product = Product.objects.create(
        category=category, title=data["title"], description=data.get("description", "")
    )
    try:
        Sku.objects.bulk_create([Sku(product=product, **row) for row in data["skus"]])
    except IntegrityError as exc:
        raise BusinessError(
            ErrorCode.INVALID_PARAM, "规格名称冲突", http_status=400
        ) from exc
    CatalogEvent.objects.create(
        product=product,
        actor=actor,
        action="create",
        snapshot=ProductOutput(product).data,
    )
    return product


@transaction.atomic
def change_status(actor, pk, version, publish):
    product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
    if product.version != version:
        raise BusinessError(
            ErrorCode.VERSION_CONFLICT, "商品已更新，请刷新后重试", http_status=409
        )
    if publish == (product.status == Product.Status.ON_SALE) or (
        not publish and product.status == Product.Status.DRAFT
    ):
        raise BusinessError(
            ErrorCode.PRODUCT_UNAVAILABLE, "当前状态无法执行此操作", http_status=409
        )
    product.status = Product.Status.ON_SALE if publish else Product.Status.OFF_SALE
    product.version += 1
    product.save(update_fields=["status", "version"])
    CatalogEvent.objects.create(
        product=product,
        actor=actor,
        action=product.status,
        snapshot={"status": product.status, "version": product.version},
    )
    return product
