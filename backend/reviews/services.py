import hashlib
import json
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from common.constants import ErrorCode
from common.exceptions import BusinessError
from orders.models import OrderItem
from .models import Review, ReviewAction


def buyer_data(review):
    item = review.order_item
    return {
        "id": str(review.pk),
        "order_item_id": str(item.pk),
        "order_no": str(item.order.order_no),
        "product_id": str(review.product_id),
        "product_title": item.snapshot["title"],
        "sku_label": item.snapshot["label"],
        "rating": review.rating,
        "content": review.content,
        "created_at": review.created_at.isoformat(),
        "status": review.status,
        "version": review.version,
        "moderation_reason": review.moderation_reason,
    }


def ops_data(review):
    item = review.order_item
    return {
        **buyer_data(review),
        "quantity": item.quantity,
        "order_status": item.order.status,
    }


def public_data(review):
    # Purchases attest eligibility; public pages never need an account identifier.
    return {
        "id": str(review.pk),
        "author_display": "已购用户",
        "rating": review.rating,
        "content": review.content,
        "created_at": review.created_at.isoformat(),
        "sku_label": review.order_item.snapshot["label"],
    }


def rating_summary(approved):
    stats = approved.aggregate(n=Count("pk"), total=Sum("rating"))
    n = stats["n"]
    average = (
        (Decimal(stats["total"]) / n).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if n
        else None
    )
    return {"count": n, "average": str(average) if n else None}


@transaction.atomic
def write(actor, operation, key, target_id, data):
    # Serialize this actor's identical commands before checking the receipt.
    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    digest = hashlib.sha256(
        json.dumps([target_id, data], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    prior = (
        ReviewAction.objects.select_related("review__order_item__order")
        .filter(actor=actor, operation=operation, key=key)
        .first()
    )
    if prior:
        if prior.digest != digest:
            raise BusinessError(
                ErrorCode.IDEMPOTENCY_CONFLICT,
                "提交标识已用于其他参数",
                http_status=409,
            )
        result = (ops_data if operation == "moderate" else buyer_data)(prior.review)
        return {
            **result,
            "status": prior.to_status,
            "version": prior.version,
            "moderation_reason": prior.reason,
        }

    if operation == "submit":
        item = get_object_or_404(
            OrderItem.objects.select_related("order", "sku"),
            pk=data["order_item_id"],
            order__user=actor,
        )
        if item.order.status != "completed":
            raise BusinessError(
                ErrorCode.ORDER_NOT_COMPLETED, "确认收货后可评价", http_status=409
            )
        if Review.objects.filter(order_item=item).exists():
            raise BusinessError(
                ErrorCode.REVIEW_DUPLICATED, "该订单项已评价", http_status=409
            )
        review = Review.objects.create(
            user=actor,
            order_item=item,
            product_id=item.sku.product_id,
            rating=data["rating"],
            content=data["content"],
        )
        previous = ""
    else:
        review = get_object_or_404(Review.objects.select_for_update(), pk=target_id)
        if review.version != data["expected_version"]:
            raise BusinessError(
                ErrorCode.VERSION_CONFLICT,
                "评价已被处理，请刷新后核对",
                http_status=409,
            )
        previous = review.status
        transition = {
            ("pending", "approve"): "approved",
            ("pending", "reject"): "rejected",
            ("approved", "hide"): "hidden",
        }.get((previous, data["action"]))
        if not transition:
            raise BusinessError(
                ErrorCode.REVIEW_STATE_INVALID,
                "当前状态不能执行此审核操作",
                http_status=409,
            )
        review.status = transition
        review.moderation_reason = data["reason"]
        review.moderated_at = timezone.now()
        review.moderated_by = actor
        review.version += 1
        review.save(
            update_fields=[
                "status",
                "moderation_reason",
                "moderated_at",
                "moderated_by",
                "version",
            ]
        )
    ReviewAction.objects.create(
        event_id=uuid4(),
        actor=actor,
        operation=operation,
        key=key,
        digest=digest,
        review=review,
        from_status=previous,
        to_status=review.status,
        version=review.version,
        reason=review.moderation_reason,
    )
    return (ops_data if operation == "moderate" else buyer_data)(review)
