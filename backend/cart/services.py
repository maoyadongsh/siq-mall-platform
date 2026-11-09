from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from catalog.models import Product, Sku
from common.constants import ErrorCode
from common.exceptions import BusinessError
from users.models import Address
from users.serializers import REGIONS
from .models import Cart, CartItem, CartOperation, Quote


def unavailable(sku, qty):
    if not sku or sku.product.status != Product.Status.ON_SALE:
        return "商品已下架或不存在"
    if qty > 99:
        return "单规格最多99件"
    if qty > sku.available_stock:
        return "可售库存不足"
    return ""


def item_data(item):
    sku = item.sku
    reason = unavailable(sku, item.quantity)
    return {
        "id": str(item.pk),
        "sku_id": str(sku.pk),
        "product_id": str(sku.product_id),
        "title": sku.product.title,
        "label": sku.label,
        "current_price": str(sku.price),
        "quantity": item.quantity,
        "selected": item.selected,
        "version": item.version,
        "available": not reason,
        "available_stock": sku.available_stock,
        "unavailable_reason": reason,
    }


def lock_cart(user):
    get_user_model().objects.select_for_update().only("pk").get(pk=user.pk)
    return Cart.objects.get_or_create(user=user)[0]


def contents(user):
    cart = Cart.objects.filter(user=user).first()
    if cart is None:
        return {"items": [], "version": 0}
    return {
        "items": [
            item_data(i)
            for i in cart.items.select_related("sku__product").order_by("id")
        ],
        "version": cart.version,
    }


def bump(cart):
    cart.version += 1
    cart.save(update_fields=["version"])


@transaction.atomic
def add_items(user, operation, key, rows):
    cart = lock_cart(user)
    prior = CartOperation.objects.filter(
        cart=cart, operation=operation, key=key
    ).first()
    if prior:
        if prior.inputs != rows:
            raise BusinessError(
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "提交标识已用于其他商品或数量",
                http_status=409,
            )
        return prior.result
    existing = {i.sku_id: i for i in cart.items.select_related("sku__product")}
    skus = Sku.objects.select_related("product").in_bulk([r["sku_id"] for r in rows])
    changes = []
    rejected = []
    for row in rows:
        pk = row["sku_id"]
        sku = skus.get(pk)
        old = existing.get(pk)
        qty = (old.quantity if old else 0) + row["quantity"]
        reason = unavailable(sku, qty)
        if not old and len(existing) >= 50:
            reason = "购物车最多50种规格"
        if reason:
            if operation == "add":
                code = (
                    ErrorCode.STOCK_NOT_ENOUGH
                    if reason == "可售库存不足"
                    else (
                        ErrorCode.PRODUCT_UNAVAILABLE
                        if not sku or sku.product.status != Product.Status.ON_SALE
                        else ErrorCode.CART_LIMIT
                    )
                )
                raise BusinessError(code, reason, http_status=409)
            rejected.append(
                {"sku_id": str(pk), "quantity": row["quantity"], "reason": reason}
            )
            continue
        if old:
            old.quantity = qty
            old.version += 1
            old.save(update_fields=["quantity", "version"])
        else:
            old = CartItem.objects.create(cart=cart, sku=sku, quantity=qty)
            existing[pk] = old
        changes.append(item_data(old))
    if changes:
        bump(cart)
    result = (
        changes[0]
        if operation == "add"
        else {
            **contents(user),
            "adjustments": rejected,
            "requires_confirmation": bool(rejected),
        }
    )
    CartOperation.objects.create(
        cart=cart, operation=operation, key=key, inputs=rows, result=result
    )
    return result


@transaction.atomic
def modify(user, pk, data, remove=False):
    cart = lock_cart(user)
    item = get_object_or_404(cart.items.select_related("sku__product"), pk=pk)
    if item.version != data["expected_version"]:
        raise BusinessError(
            ErrorCode.VERSION_CONFLICT, "购物车已更新，请刷新后核对", http_status=409
        )
    if remove:
        item.delete()
        result = None
    else:
        qty = data.get("quantity", item.quantity)
        if "quantity" in data or data.get("selected"):
            reason = unavailable(item.sku, qty)
            if reason:
                raise BusinessError(
                    ErrorCode.PRODUCT_UNAVAILABLE, reason, http_status=409
                )
        item.quantity = qty
        item.selected = data.get("selected", item.selected)
        item.version += 1
        item.save(update_fields=["quantity", "selected", "version"])
        result = item_data(item)
    bump(cart)
    return result


def calculate_quote(user, data, *, for_order=False):
    from promotions.services import apply_discount

    address = get_object_or_404(Address, user=user, pk=data["address_id"])
    code = address.region_code
    if (
        REGIONS["province_list"].get(code[:2] + "0000"),
        REGIONS["city_list"].get(code[:4] + "00"),
        REGIONS["county_list"].get(code),
    ) != (address.province, address.city, address.district):
        raise BusinessError(
            ErrorCode.INVALID_PARAM, "请重新选择地址的配送地区", http_status=400
        )
    skus = Sku.objects.select_related("product").in_bulk(
        [r["sku_id"] for r in data["items"]]
    )
    total = Decimal("0.00")
    lines = []
    for row in data["items"]:
        sku = skus.get(row["sku_id"])
        qty = row["quantity"]
        reason = unavailable(sku, qty)
        if reason:
            raise BusinessError(
                (
                    ErrorCode.STOCK_NOT_ENOUGH
                    if reason == "可售库存不足"
                    else ErrorCode.PRODUCT_UNAVAILABLE
                ),
                reason,
                http_status=409,
            )
        amount = sku.price * qty
        lines.append(
            {
                "sku_id": str(sku.pk),
                "title": sku.product.title,
                "label": sku.label,
                "quantity": qty,
                "unit_price": str(sku.price),
                "line_amount": str(amount),
                "discount_allocated": "0.00",
            }
        )
        total += amount
    freight = (
        Decimal("0.00")
        if total >= settings.CART_FREE_SHIPPING_THRESHOLD
        else settings.CART_BASE_FREIGHT
    )
    if total + freight > Decimal("9999999999.99"):
        raise BusinessError(
            ErrorCode.INVALID_PARAM, "订单金额超出上限", http_status=400
        )
    summary = {
        "id": str(address.pk),
        "version": address.version,
        "recipient": address.recipient,
        "phone_masked": address.phone[:3] + "****" + address.phone[-4:],
        "region": address.province + address.city + address.district,
    }
    discount, selected, options, rejected = apply_discount(
        user,
        data.get("user_coupon_id"),
        lines,
        skus,
        list_options=not for_order,
        lock=for_order,
    )
    amounts = {
        "goods_amount": str(total),
        "freight_amount": str(freight),
        "discount_amount": str(discount),
        "payable_amount": str(total + freight - discount),
        "currency": "CNY",
    }
    body = {
        "items": lines,
        **amounts,
        "address_summary": summary,
        "selected_coupon": selected,
        "available_coupons": options,
        "unavailable_coupons": rejected,
    }
    snapshot = {
        "items": lines,
        **amounts,
        "address_summary": {"id": str(address.pk), "version": address.version},
        "shipping_version": settings.CART_SHIPPING_VERSION,
        "shipping_threshold": str(settings.CART_FREE_SHIPPING_THRESHOLD),
        "base_freight": str(settings.CART_BASE_FREIGHT),
    }
    if selected:
        snapshot["coupon"] = selected
    return body, snapshot, address


@transaction.atomic
def quote(user, data):
    body, snapshot, _ = calculate_quote(user, data)
    expires = timezone.now() + timedelta(minutes=5)
    record = Quote.objects.create(user=user, expires_at=expires, snapshot=snapshot)
    return {**body, "quote_id": str(record.pk), "expires_at": expires.isoformat()}
