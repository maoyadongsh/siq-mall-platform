from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from common.constants import ErrorCode
from common.exceptions import BusinessError
from .models import Template, Coupon, Receipt, Revision


def conflict(message, code=ErrorCode.COUPON_NOT_USABLE):
    raise BusinessError(code, message, http_status=409)


def terms(t):
    return {
        "template_id": str(t.pk),
        "template_version": t.version,
        "name": t.name,
        "type": t.type,
        "threshold_amount": str(t.threshold_amount),
        "reduction_amount": (
            str(t.reduction_amount) if t.reduction_amount is not None else None
        ),
        "cap_amount": str(t.cap_amount) if t.cap_amount is not None else None,
        "discount_bps": t.discount_bps,
        "scope": t.scope,
        "product_ids": sorted(str(p.pk) for p in t.products.all()),
        "start_at": t.start_at.isoformat(),
        "end_at": t.end_at.isoformat(),
    }


def template_data(t):
    return {
        **terms(t),
        "id": str(t.pk),
        "version": t.version,
        "status": t.status,
        "total": t.total,
        "issued": t.issued,
        "per_user_limit": t.per_user_limit,
        "claim_start_at": t.claim_start_at.isoformat(),
        "claim_end_at": t.claim_end_at.isoformat(),
    }


def coupon_data(c, now):
    state = "expired" if c.status == "unused" and c.end_at <= now else c.status
    return {
        **c.terms,
        "id": str(c.pk),
        "serial_no": str(c.serial_no),
        "status": state,
        "order_no": str(c.order.order_no) if c.order_id else None,
    }


@transaction.atomic
def command(actor, pk, op, key, data):
    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    receipt = Receipt.objects.filter(actor=actor, operation=op, key=key).first()
    if receipt:
        if receipt.template_id != pk or receipt.inputs != data:
            conflict("相同提交标识的参数不同", ErrorCode.IDEMPOTENCY_CONFLICT)
        return receipt.result
    t = get_object_or_404(Template.objects.select_for_update(), pk=pk)
    now = timezone.now()
    if op == "claim":
        if t.status != "active" or not t.claim_start_at <= now < t.claim_end_at:
            conflict("当前不可领取", ErrorCode.COUPON_NOT_CLAIMABLE)
        slot = Coupon.objects.filter(user=actor, template=t).count() + 1
        if slot > t.per_user_limit:
            conflict("已达到每人限领数量", ErrorCode.COUPON_NOT_CLAIMABLE)
        if not Template.objects.filter(pk=pk, issued__lt=F("total")).update(
            issued=F("issued") + 1
        ):
            conflict("优惠券已领完", ErrorCode.COUPON_NOT_CLAIMABLE)
        c = Coupon.objects.create(
            user=actor,
            template=t,
            claim_index=slot,
            terms=terms(t),
            start_at=t.start_at,
            end_at=t.end_at,
        )
        result = coupon_data(c, now)
    else:
        if t.version != data["expected_version"]:
            conflict("模板已更新，请刷新", ErrorCode.VERSION_CONFLICT)
        if op == "publish" and t.status == "draft" and now < t.claim_end_at:
            t.status = "active"
        elif op == "stop" and t.status == "active":
            t.status = "stopped"
        else:
            conflict("当前状态或时段不允许此操作")
        t.version += 1
        t.save(update_fields=["status", "version"])
        result = template_data(t)
        Revision.objects.create(
            template=t, version=t.version, actor=actor, action=op, snapshot=result
        )
    Receipt.objects.create(
        actor=actor, template=t, operation=op, key=key, inputs=data, result=result
    )
    return result


def evaluate(c, lines, products, now):
    if c.status == "reserved":
        return "已被待付款订单占用", {}
    if c.status == "used":
        return "已核销", {}
    if c.status == "expired" or now >= c.end_at:
        return "已过期", {}
    if now < c.start_at:
        return "尚未生效", {}
    rule = c.terms
    allowed = set(rule["product_ids"])
    cents = {
        int(line["sku_id"]): int(Decimal(line["line_amount"]) * 100)
        for line in lines
        if rule["scope"] == "all"
        or str(products[int(line["sku_id"])].product_id) in allowed
    }
    total = sum(cents.values())
    if not total:
        return "当前商品不在可优惠范围", {}
    if total < int(Decimal(rule["threshold_amount"]) * 100):
        return "适用商品金额未达门槛", {}
    if rule["type"] == "fixed":
        discount = int(Decimal(rule["reduction_amount"]) * 100)
    else:
        discount = int(
            (Decimal(total) * rule["discount_bps"] / 10000).quantize(
                Decimal(1), rounding=ROUND_HALF_UP
            )
        )
        discount = min(discount, int(Decimal(rule["cap_amount"]) * 100))
    discount = min(discount, total)
    if not discount:
        return "当前优惠不足一分", {}
    allocations = {k: discount * v // total for k, v in cents.items()}
    for k in sorted(cents, key=lambda k: (-(discount * cents[k] % total), k))[
        : discount - sum(allocations.values())
    ]:
        allocations[k] += 1
    return "", allocations


def apply_discount(user, coupon_id, lines, products, *, list_options, lock):
    now = timezone.now()
    wallet = Coupon.objects.filter(user=user)
    options = []
    rejected = []
    if list_options:
        # Full wallet is independently paginated; quote offers the earliest-expiring 100.
        for c in wallet.filter(status="unused", end_at__gt=now).order_by(
            "end_at", "pk"
        )[:100]:
            reason, parts = evaluate(c, lines, products, now)
            if reason:
                rejected.append(
                    {"id": str(c.pk), "name": c.terms["name"], "reason": reason}
                )
            else:
                options.append(
                    {
                        "id": str(c.pk),
                        "name": c.terms["name"],
                        "discount_amount": money(sum(parts.values())),
                    }
                )
    if coupon_id is None:
        return Decimal("0.00"), None, options, rejected
    c = get_object_or_404(wallet.select_for_update() if lock else wallet, pk=coupon_id)
    reason, parts = evaluate(c, lines, products, now)
    if reason:
        conflict(reason)
    for line in lines:
        line["discount_allocated"] = money(parts.get(int(line["sku_id"]), 0))
    discount = money(sum(parts.values()))
    return (
        Decimal(discount),
        {**c.terms, "id": str(c.pk), "discount_amount": discount},
        options,
        rejected,
    )


def money(cents):
    return format(Decimal(cents) / 100, ".2f")


def reserve(order):
    if order.coupon_snapshot:
        now = timezone.now()
        changed = Coupon.objects.filter(
            pk=order.coupon_snapshot["id"],
            user=order.user,
            status="unused",
            start_at__lte=now,
            end_at__gt=now,
        ).update(status="reserved", order=order, reserved_at=now)
        if changed != 1:
            conflict("优惠券状态已变化，请重新试算")


def finish(order, paid):
    if not order.coupon_snapshot:
        return
    coupon = (
        Coupon.objects.select_for_update()
        .filter(order=order, status="reserved")
        .first()
    )
    if not coupon:
        conflict("订单占券状态异常")
    now = timezone.now()
    if paid:
        coupon.status = "used"
        coupon.used_at = now
    else:
        coupon.status = "expired" if now >= coupon.end_at else "unused"
        coupon.order = None
        coupon.reserved_at = None
    coupon.save(update_fields=["status", "order", "reserved_at", "used_at"])
