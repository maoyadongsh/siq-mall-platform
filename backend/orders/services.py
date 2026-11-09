import hashlib
import json
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import OperationalError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from cart.models import Cart, CartItem, Quote
from promotions.services import reserve as reserve_coupon, finish as finish_coupon
from cart.services import calculate_quote
from catalog.models import Product, Sku
from common.constants import ErrorCode as Code
from common.exceptions import BusinessError
from .models import (
    Event,
    Operation,
    Order,
    OrderActivity,
    OrderItem,
    Payment,
    Settlement,
    StockMovement,
)


def conflict(code, message):
    raise BusinessError(code, message, http_status=409)


def summary(order, ops=False):
    actions = []
    if order.status == "pending" and not ops:
        actions = ["cancel"]
        if settings.DEMO_PAYMENT_ENABLED and timezone.now() < order.expires_at:
            actions.append("pay")
    if order.status == "completed" and not ops:
        actions = ["review"]
    if order.status == "paid" and ops:
        actions = ["ship"]
    if order.status == "shipped" and not ops:
        actions = ["receive"]
    return {
        "order_no": str(order.order_no),
        "status": order.status,
        "version": order.version,
        **order.amounts,
        "expires_at": order.expires_at.isoformat(),
        "created_at": order.created_at.isoformat(),
        "allowed_actions": actions,
    }


def payment_data(payment, order):
    return {
        "pay_no": str(payment.pay_no),
        "order_no": str(order.order_no),
        "status": payment.status,
        "order_status": order.status,
        "mode": "demo",
        "amount": str(payment.amount),
        "expires_at": order.expires_at.isoformat(),
    }


def detail(order, ops=False):
    payment = (
        order.payments.filter(status="success").first()
        or order.payments.order_by("-id").first()
    )
    return {
        **summary(order, ops),
        "items": [
            {**i.snapshot, "order_item_id": str(i.pk)}
            for i in order.items.order_by("id")
        ],
        "address_snapshot": order.address_snapshot,
        "shipment": order.shipment,
        "coupon_snapshot": order.coupon_snapshot,
        "payment_summary": payment_data(payment, order) if payment else None,
        "events": [
            {"type": e.kind, "at": e.occurred_at.isoformat(), "reason": e.reason}
            for e in order.events.order_by("id")
        ],
    }


def lock_stock(ids):
    products = sorted(
        set(Sku.objects.filter(pk__in=ids).values_list("product_id", flat=True))
    )
    list(
        Product.objects.filter(pk__in=products)
        .order_by("pk")
        .select_for_update()
        .values_list("pk", flat=True)
    )
    return {
        s.pk: s
        for s in Sku.objects.filter(pk__in=ids).order_by("pk").select_for_update()
    }


def move(item, sku, kind):
    quantity = item.quantity
    available, reserved = {
        "reserve": (-quantity, quantity),
        "release": (quantity, -quantity),
        "consume": (0, -quantity),
    }[kind]
    changed = Sku.objects.filter(
        pk=sku.pk,
        available_stock__gte=max(0, -available),
        reserved_stock__gte=max(0, -reserved),
    ).update(
        available_stock=F("available_stock") + available,
        reserved_stock=F("reserved_stock") + reserved,
        version=F("version") + 1,
    )
    if changed != 1:
        conflict(Code.STOCK_NOT_ENOUGH, "库存已变化，请重新核对")
    StockMovement.objects.create(
        item=item, kind=kind, available_delta=available, reserved_delta=reserved
    )


def transition(order, status, actor, reason=""):
    order.status = status
    order.version += 1
    order.save(update_fields=["status", "version", "shipment"])
    Event.objects.create(
        order=order, kind="order." + status, reason=reason, actor=actor
    )


def locked_order(actor, no, ops=False):
    rows = Order.objects.select_for_update()
    if not ops:
        rows = rows.filter(user=actor)
    return get_object_or_404(rows, order_no=no)


def replay(receipt):
    result = dict(receipt.result)
    if result.pop("_address", False):
        result["address_snapshot"] = receipt.order.address_snapshot
    if result.pop("_shipment", False):
        result["shipment"] = receipt.order.shipment
    return result


@transaction.atomic
def run_once(actor, operation, key, inputs, command):
    # Same actor writes serialize before looking up a key, including the first write.
    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    digest = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    prior = Operation.objects.filter(user=actor, operation=operation, key=key).first()
    if prior:
        if prior.digest != digest:
            conflict(Code.IDEMPOTENCY_CONFLICT, "同一提交标识不能用于其他操作参数")
        return replay(prior)
    order, result = command()
    snapshot = dict(result)
    if "address_snapshot" in snapshot:
        snapshot.pop("address_snapshot")
        snapshot["_address"] = True
    if snapshot.get("shipment"):
        snapshot.pop("shipment")
        snapshot["_shipment"] = True
    Operation.objects.create(
        user=actor,
        operation=operation,
        key=key,
        digest=digest,
        order=order,
        resource_id=result.get("pay_no", order.order_no),
        result=snapshot,
    )
    return result


def execute(actor, operation, key, data, command):
    for attempt in range(3):
        try:
            return run_once(actor, operation, key, data, command)
        except OperationalError as exc:
            if exc.args[0] not in (1205, 1213):
                raise
            if attempt == 2:
                conflict(Code.OPERATION_BUSY, "请求处理中，请使用原提交标识重试")
            time.sleep(0.04 * (attempt + 1))


def place(user, data):
    quote_id = data["quote_id"]
    prior = Order.objects.filter(user=user, intent_id=data["intent_id"]).first()
    if prior:
        if prior.quote_id != quote_id:
            conflict(Code.IDEMPOTENCY_CONFLICT, "购买标识已绑定另一份报价")
        return prior, detail(prior)
    q = get_object_or_404(Quote, user=user, id=quote_id)
    if Order.objects.filter(quote=q).exists():
        conflict(Code.DUPLICATE_SUBMIT, "此报价已生成订单，请查看我的订单")
    old = q.snapshot
    lines = [
        {"sku_id": int(r["sku_id"]), "quantity": r["quantity"]} for r in old["items"]
    ]
    stock = lock_stock([r["sku_id"] for r in lines])
    if timezone.now() >= q.expires_at:
        conflict(Code.QUOTE_EXPIRED, "报价已过期，请重新试算")
    body, current, address = calculate_quote(
        user,
        {
            "address_id": old["address_summary"]["id"],
            "items": lines,
            "user_coupon_id": (old.get("coupon") or {}).get("id"),
        },
        for_order=True,
    )
    if current != old:
        conflict(Code.QUOTE_CHANGED, "价格、地址或配送规则已变化，请重新试算并确认")
    order = Order.objects.create(
        user=user,
        quote=q,
        intent_id=data["intent_id"],
        **{
            k: body[k]
            for k in (
                "goods_amount",
                "freight_amount",
                "discount_amount",
                "payable_amount",
                "currency",
            )
        },
        coupon_snapshot=body["selected_coupon"],
        address_snapshot={
            k: getattr(address, k)
            for k in (
                "recipient",
                "phone",
                "province",
                "city",
                "district",
                "detail",
                "region_code",
            )
        },
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    reserve_coupon(order)
    covers = {
        p.pk: p.cover.file.url if p.cover_id else None
        for p in Product.objects.filter(
            pk__in={s.product_id for s in stock.values()}
        ).select_related("cover")
    }
    for line in body["items"]:
        sku = stock[int(line["sku_id"])]
        item = OrderItem.objects.create(
            order=order,
            sku=sku,
            quantity=line["quantity"],
            snapshot={
                **line,
                "product_id": str(sku.product_id),
                "image_url": covers[sku.product_id],
            },
        )
        move(item, sku, "reserve")
    cart = Cart.objects.filter(user=user).first()
    if cart:
        removed = 0
        for row in lines:
            removed += CartItem.objects.filter(
                cart=cart, selected=True, **row
            ).delete()[0]
        if removed:
            Cart.objects.filter(pk=cart.pk).update(version=F("version") + 1)
    Event.objects.create(order=order, kind="order.created", actor=user)
    return order, detail(order)


def settle_stock(order, kind):
    lines = list(order.items.order_by("sku_id"))
    stock = lock_stock([i.sku_id for i in lines])
    for item in lines:
        move(item, stock[item.sku_id], kind)


def cancel_locked(order, actor, reason):
    if order.status == "canceled":
        return
    if order.status != "pending":
        conflict(Code.ORDER_STATUS_INVALID, "仅待付款订单可以取消")
    settle_stock(order, "release")
    finish_coupon(order, False)
    transition(order, "canceled", actor, reason)


def cancel(user, no, data):
    order = locked_order(user, no)
    cancel_locked(order, user, data["reason"])
    return order, detail(order)


def require_payable(order):
    if order.status != "pending":
        conflict(Code.ORDER_STATUS_INVALID, "订单当前不可付款")
    if timezone.now() >= order.expires_at:
        conflict(Code.ORDER_EXPIRED, "订单已过付款期限")


def init_payment(user, data):
    order = locked_order(user, data["order_no"])
    require_payable(order)
    payment = order.payments.filter(status="init").order_by(
        "id"
    ).first() or Payment.objects.create(
        order=order, amount=order.amounts["payable_amount"]
    )
    return order, payment_data(payment, order)


def simulate(user, no, data):
    ref = get_object_or_404(
        Payment.objects.filter(order__user=user).values("order__order_no"), pay_no=no
    )
    order = locked_order(user, ref["order__order_no"])
    payment = Payment.objects.select_for_update().get(pay_no=no, order=order)
    if payment.status == data["outcome"]:
        return order, payment_data(payment, order)
    if payment.status != "init":
        conflict(Code.PAYMENT_STATUS_INVALID, "此支付尝试已结束")
    require_payable(order)
    if str(payment.amount) != order.amounts["payable_amount"]:
        conflict(Code.PAYMENT_AMOUNT_MISMATCH, "支付金额与订单不一致")
    payment.status = data["outcome"]
    payment.save(update_fields=["status"])
    if payment.status == "success":
        Settlement.objects.create(order=order, payment=payment)
        settle_stock(order, "consume")
        finish_coupon(order, True)
        transition(order, "paid", user)
    return order, payment_data(payment, order)


def ship(actor, no, data):
    order = locked_order(actor, no, ops=True)
    if order.version != data["expected_version"]:
        conflict(Code.VERSION_CONFLICT, "订单已更新，请刷新后核对")
    if order.status != "paid":
        conflict(Code.ORDER_STATUS_INVALID, "只有已付款订单可发货")
    order.shipment = {
        "carrier": data["carrier"],
        "tracking_no": data["tracking_no"],
        "shipped_at": timezone.now().isoformat(),
    }
    transition(order, "shipped", actor)
    return order, detail(order, True)


def receive(user, no):
    order = locked_order(user, no)
    if order.status == "completed":
        return order, detail(order)
    if order.status != "shipped":
        conflict(Code.ORDER_STATUS_INVALID, "只有已发货订单可确认收货")
    transition(order, "completed", user)
    return order, detail(order)


@transaction.atomic
def expire_one(pk):
    order = Order.objects.select_for_update().get(pk=pk)
    if order.status == "pending" and order.expires_at <= timezone.now():
        cancel_locked(order, None, "timeout")
        return True
    return False


@transaction.atomic
def deliver_one(pk):
    event = Event.objects.select_for_update().get(pk=pk)
    if event.delivered_at:
        return False
    OrderActivity.objects.get_or_create(event=event)
    event.delivered_at = timezone.now()
    event.save(update_fields=["delivered_at"])
    return True
