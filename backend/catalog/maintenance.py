"""商品维护事务。商品先于 SKU 加锁，调整重放按操作者隔离。"""

from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Min
from django.shortcuts import get_object_or_404

from common.constants import ErrorCode
from common.exceptions import BusinessError
from .models import CatalogEvent, Category, MediaAsset, Product, Sku, StockAdjustment


def invalid(message, status=400):
    return BusinessError(ErrorCode.INVALID_PARAM, message, http_status=status)


def upload_image(actor, file):
    if file.size > 5 * 1024 * 1024:
        raise invalid("图片不能超过5MB", 413)
    try:
        with Image.open(file, formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > 20_000_000 or getattr(
                image, "is_animated", False
            ):
                raise invalid("请选择不超过2000万像素的静态图片")
            image.load()
            normalized = ImageOps.exif_transpose(image).convert("RGBA")
            normalized.thumbnail((1920, 1920))
            normalized.info.clear()
            output = BytesIO()
            normalized.save(output, format="WEBP", quality=88)
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise invalid("请选择有效的 JPEG、PNG 或 WebP 图片") from exc
    asset = MediaAsset(
        width=normalized.width, height=normalized.height, uploaded_by=actor
    )
    asset.file.save(f"{uuid4().hex}.webp", ContentFile(output.getvalue()), save=False)
    try:
        asset.save()
    except Exception:
        asset.file.delete(save=False)
        raise
    return asset


def check_version(obj, expected):
    if obj.version != expected:
        raise BusinessError(
            ErrorCode.VERSION_CONFLICT,
            "内容已更新，请刷新后核对再提交",
            http_status=409,
        )


def bump(product):
    product.version += 1
    product.save(update_fields=["version"])


@transaction.atomic
def edit_product(actor, pk, data):
    obj = get_object_or_404(Product.objects.select_for_update(), pk=pk)
    check_version(obj, data["expected_version"])
    before = {
        "title": obj.title,
        "description": obj.description,
        "category": obj.category.name,
        "cover_id": obj.cover_id,
    }
    for name in ("title", "description"):
        if name in data:
            setattr(obj, name, data[name])
    if "category" in data:
        obj.category, _ = Category.objects.get_or_create(name=data["category"])
    if "cover_id" in data:
        obj.cover = (
            get_object_or_404(MediaAsset, pk=data["cover_id"])
            if data["cover_id"]
            else None
        )
    obj.version += 1
    obj.save()
    CatalogEvent.objects.create(
        product=obj,
        actor=actor,
        action="product_edit",
        snapshot={
            "before": before,
            "after": {
                "title": obj.title,
                "description": obj.description,
                "category": obj.category.name,
                "cover_id": obj.cover_id,
            },
        },
    )
    return obj


def lock_variant(pk):
    product_id = get_object_or_404(Sku.objects.only("product_id"), pk=pk).product_id
    product = Product.objects.select_for_update().get(pk=product_id)
    sku = Sku.objects.select_for_update().get(pk=pk, product=product)
    return product, sku


@transaction.atomic
def edit_sku(actor, pk, data):
    product, sku = lock_variant(pk)
    check_version(sku, data["expected_version"])
    before = {"label": sku.label, "price": str(sku.price)}
    for name in ("label", "price"):
        if name in data:
            setattr(sku, name, data[name])
    if product.skus.exclude(pk=pk).filter(label__iexact=sku.label).exists():
        raise invalid("规格名称重复")
    sku.version += 1
    try:
        sku.save(update_fields=["label", "price", "version"])
    except IntegrityError as exc:
        raise invalid("规格名称冲突") from exc
    product.min_price = product.skus.aggregate(value=Min("price"))["value"]
    product.save(update_fields=["min_price"])
    bump(product)
    CatalogEvent.objects.create(
        product=product,
        actor=actor,
        action="sku_edit",
        snapshot={
            "sku_id": str(pk),
            "before": before,
            "after": {"label": sku.label, "price": str(sku.price)},
            "reason": data["reason"],
        },
    )
    return sku


def replay_adjustment(prior, pk, data):
    if prior.sku_id != pk or any(
        getattr(prior, k) != data[k] for k in ("expected_version", "reason", "delta")
    ):
        raise BusinessError(
            ErrorCode.IDEMPOTENCY_CONFLICT, "提交标识已用于其他调整", http_status=409
        )
    return prior


@transaction.atomic
def adjust_stock(actor, pk, key, data):
    product, sku = lock_variant(pk)
    prior = StockAdjustment.objects.filter(actor=actor, key=key).first()
    if prior:
        return replay_adjustment(prior, pk, data)
    check_version(sku, data["expected_version"])
    after = sku.available_stock + data["delta"]
    if after < 0:
        raise BusinessError(
            ErrorCode.STOCK_NOT_ENOUGH, "扣减数量超过当前可售库存", http_status=409
        )
    if after + sku.reserved_stock > 2147483647:
        raise invalid("库存超出上限")
    row, created = StockAdjustment.objects.get_or_create(
        actor=actor,
        key=key,
        defaults={
            "operator": actor.get_username(),
            "sku": sku,
            "before": sku.available_stock,
            "after": after,
            **data,
        },
    )
    if not created:
        return replay_adjustment(row, pk, data)
    sku.available_stock = after
    sku.version += 1
    sku.save(update_fields=["available_stock", "version"])
    bump(product)
    return row
