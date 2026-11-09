import hashlib
import json
import re

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from common.constants import ErrorCode as Code
from common.exceptions import BusinessError
from content.models import ContentEvent
from orders.models import Event
from reviews.models import ReviewAction

from .apps import TEMPLATE_VARIABLES
from .models import (
    Notification,
    NotificationConsumption,
    NotificationSequence,
    NotificationSubscription,
    NotificationTemplate,
    NotificationTemplateAction,
    NotificationTemplatePointer,
)

CONSUMER = "notifications.inbox"
NOTICE_TYPES = ("order", "support", "system")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
SAMPLES = {
    "order_no": "DEMO-PREVIEW",
    "review_status": "已公开",
    "announcement_title": "示例公告",
}


class TemplateConfigurationError(Exception):
    pass


def conflict(code, message):
    raise BusinessError(code, message, http_status=409)


def render(template, context):
    def replace(match):
        name = match.group(1)
        if name not in template.variables or name not in TEMPLATE_VARIABLES.get(
            template.event_type, set()
        ):
            raise TemplateConfigurationError("模板包含未授权变量")
        if name not in context or context[name] is None:
            raise TemplateConfigurationError("模板变量不完整")
        return str(context[name])

    try:
        title = PLACEHOLDER.sub(replace, template.title)
        body = PLACEHOLDER.sub(replace, template.body)
    except TemplateConfigurationError:
        raise
    if not title or len(title) > 100 or not body or len(body) > 1000:
        raise TemplateConfigurationError("模板渲染结果超出字段限制")
    return title, body


def validate_template(event_type, title, body, variables):
    allowed = TEMPLATE_VARIABLES.get(event_type)
    if allowed is None:
        raise BusinessError(Code.TEMPLATE_INVALID, "不支持的通知事件")
    if not isinstance(variables, list) or any(
        not isinstance(item, str) for item in variables
    ):
        raise BusinessError(Code.TEMPLATE_INVALID, "模板变量必须是字符串数组")
    if set(variables) - allowed:
        raise BusinessError(Code.TEMPLATE_INVALID, "模板变量超出事件白名单")
    placeholders = set(PLACEHOLDER.findall(title + body))
    if not placeholders <= set(variables):
        raise BusinessError(Code.TEMPLATE_INVALID, "模板使用了未声明变量")
    return title, body


def template_data(template):
    pointer = NotificationTemplatePointer.objects.filter(
        event_type=template.event_type, channel=template.channel, template=template
    ).first()
    sample = {key: SAMPLES[key] for key in TEMPLATE_VARIABLES[template.event_type]}
    title, body = render(template, sample)
    return {
        "id": str(template.pk),
        "event_type": template.event_type,
        "channel": template.channel,
        "version": template.version,
        "title": template.title,
        "body": template.body,
        "variables": template.variables,
        "enabled": template.enabled,
        "active": pointer is not None,
        "created_at": template.created_at.isoformat(),
        "supported_variables": sorted(TEMPLATE_VARIABLES[template.event_type]),
        "preview": {"title": title, "body": body},
    }


@transaction.atomic
def revise_template(actor, template_id, data):
    current = get_object_or_404(
        NotificationTemplate.objects.select_for_update(), pk=template_id
    )
    latest = (
        NotificationTemplate.objects.select_for_update()
        .filter(event_type=current.event_type, channel=current.channel)
        .order_by("-version")
        .first()
    )
    if latest.version != data["expected_version"] or current.version != latest.version:
        conflict(Code.VERSION_CONFLICT, "模板已有新版本，请刷新后编辑")
    validate_template(
        current.event_type, data["title"], data["body"], data["variables"]
    )
    template = NotificationTemplate.objects.create(
        event_type=current.event_type,
        channel=current.channel,
        version=latest.version + 1,
        title=data["title"],
        body=data["body"],
        variables=data["variables"],
        editor=actor,
    )
    return template_data(template)


@transaction.atomic
def activate_template(actor, template_id, data, action_key):
    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    digest = hashlib.sha256(
        json.dumps([str(template_id), data], sort_keys=True).encode()
    ).hexdigest()
    prior = NotificationTemplateAction.objects.filter(
        actor=actor, operation="activate", key=action_key
    ).first()
    if prior:
        if prior.digest != digest:
            conflict(Code.IDEMPOTENCY_CONFLICT, "提交标识已用于其他模板或版本")
        return prior.result
    desired = get_object_or_404(NotificationTemplate, pk=template_id)
    if desired.version != data["version"]:
        conflict(Code.VERSION_CONFLICT, "启用版本与编辑内容不一致")
    pointer = get_object_or_404(
        NotificationTemplatePointer.objects.select_for_update(),
        event_type=desired.event_type,
        channel=desired.channel,
    )
    if pointer.template.version != data["expected_version"]:
        conflict(Code.VERSION_CONFLICT, "当前启用模板已变化，请刷新后核对")
    validate_template(
        desired.event_type, desired.title, desired.body, desired.variables
    )
    template_data(desired)
    if pointer.template_id != desired.pk:
        desired.enabled = True
        desired.editor = actor
        desired.save(update_fields=["enabled", "editor"])
        pointer.template = desired
        pointer.save(update_fields=["template"])
    result = template_data(desired)
    NotificationTemplateAction.objects.create(
        actor=actor,
        operation="activate",
        key=action_key,
        digest=digest,
        template=desired,
        result=result,
    )
    return result


def active_template(event_type):
    pointer = get_object_or_404(
        NotificationTemplatePointer.objects.select_related("template"),
        event_type=event_type,
        channel="inbox",
        template__enabled=True,
    )
    return pointer.template


@transaction.atomic
def create_notice(
    user, event_id, event_type, notice_type, target_type, target_id, context
):
    get_user_model().objects.select_for_update().only("pk").get(pk=user.pk)
    existing = Notification.objects.filter(
        user=user, event_id=event_id, type=notice_type
    ).first()
    if existing:
        return existing
    template = active_template(event_type)
    title, body = render(template, context)
    sequence, _ = NotificationSequence.objects.select_for_update().get_or_create(
        user=user
    )
    sequence.last_seq += 1
    sequence.save(update_fields=["last_seq"])
    return Notification.objects.create(
        user=user,
        recipient_seq=sequence.last_seq,
        event_id=event_id,
        type=notice_type,
        title=title,
        body=body,
        target_type=target_type,
        target_id=str(target_id),
    )


@transaction.atomic
def deliver_order_event(pk):
    event = get_object_or_404(
        Event.objects.select_for_update().select_related("order__user"), pk=pk
    )
    if NotificationConsumption.objects.filter(
        event_id=event.event_id, consumer=CONSUMER
    ).exists():
        return False
    create_notice(
        event.order.user,
        event.event_id,
        event.kind,
        "order",
        "order",
        event.order.order_no,
        {"order_no": str(event.order.order_no)},
    )
    NotificationConsumption.objects.create(event_id=event.event_id, consumer=CONSUMER)
    return True


@transaction.atomic
def deliver_review_action(pk):
    action = get_object_or_404(
        ReviewAction.objects.select_for_update().select_related("review__user"),
        pk=pk,
        event_id__isnull=False,
    )
    if NotificationConsumption.objects.filter(
        event_id=action.event_id, consumer=CONSUMER
    ).exists():
        return False
    labels = {"approved": "已公开", "rejected": "未通过", "hidden": "已隐藏"}
    create_notice(
        action.review.user,
        action.event_id,
        "review.moderated",
        "system",
        "review",
        action.review_id,
        {"review_status": labels[action.to_status]},
    )
    NotificationConsumption.objects.create(event_id=action.event_id, consumer=CONSUMER)
    return True


@transaction.atomic
def deliver_content_event(pk):
    event = get_object_or_404(
        ContentEvent.objects.select_for_update().select_related("revision__content"),
        pk=pk,
    )
    if NotificationConsumption.objects.filter(
        event_id=event.event_id, consumer=CONSUMER
    ).exists():
        return False
    for user in get_user_model().objects.filter(is_active=True).order_by("pk"):
        create_notice(
            user,
            event.event_id,
            event.kind,
            "system",
            "announcement",
            event.revision.content_id,
            {"announcement_title": event.revision.title},
        )
    NotificationConsumption.objects.create(event_id=event.event_id, consumer=CONSUMER)
    return True


def notice_data(row):
    return {
        "id": str(row.pk),
        "recipient_seq": str(row.recipient_seq),
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "created_at": row.created_at.isoformat(),
        "is_read": row.read_at is not None,
        "read_at": row.read_at.isoformat() if row.read_at else None,
    }


def unread(user):
    counts = dict(
        Notification.objects.filter(user=user, read_at__isnull=True)
        .values("type")
        .annotate(total=Count("pk"))
        .values_list("type", "total")
    )
    by_type = {key: counts.get(key, 0) for key in NOTICE_TYPES}
    return {"total": sum(by_type.values()), "by_type": by_type}


def watermark(user, notice_type):
    sequence, _ = NotificationSequence.objects.get_or_create(user=user)
    return signing.dumps(
        {"user": user.pk, "type": notice_type or "", "seq": sequence.last_seq},
        salt="notifications.read",
    )


def cursor_token(user, notice_type, row):
    return signing.dumps(
        {
            "user": user.pk,
            "type": notice_type or "",
            "seq": row.recipient_seq,
            "id": row.pk,
        },
        salt="notifications.cursor",
    )


def load_token(user, notice_type, token, salt):
    try:
        value = signing.loads(token, salt=salt, max_age=3600)
    except signing.BadSignature as exc:
        raise BusinessError(
            Code.NOTICE_CURSOR_INVALID, "分页或已读凭证无效，请刷新"
        ) from exc
    if value.get("user") != user.pk or value.get("type") != (notice_type or ""):
        raise BusinessError(
            Code.NOTICE_CURSOR_INVALID, "分页或已读凭证与当前筛选不一致"
        )
    return value


def page(user, notice_type, cursor, limit):
    rows = Notification.objects.filter(user=user)
    if notice_type:
        rows = rows.filter(type=notice_type)
    if cursor:
        value = load_token(user, notice_type, cursor, "notifications.cursor")
        rows = rows.filter(
            Q(recipient_seq__lt=value["seq"])
            | Q(recipient_seq=value["seq"], pk__lt=value["id"])
        )
    selected = list(rows.order_by("-recipient_seq", "-id")[: limit + 1])
    has_more = len(selected) > limit
    selected = selected[:limit]
    return {
        "results": [notice_data(row) for row in selected],
        "next_cursor": (
            cursor_token(user, notice_type, selected[-1])
            if selected and has_more
            else None
        ),
        "has_more": has_more,
        "read_watermark": watermark(user, notice_type),
    }


@transaction.atomic
def mark_read(user, data):
    rows = Notification.objects.filter(user=user, read_at__isnull=True)
    if "ids" in data:
        rows = rows.filter(pk__in=data["ids"])
    else:
        notice_type = data.get("type") or ""
        value = load_token(user, notice_type, data["watermark"], "notifications.read")
        rows = rows.filter(recipient_seq__lte=value["seq"])
        if notice_type:
            rows = rows.filter(type=notice_type)
    changed = rows.update(read_at=timezone.now())
    return {"updated_count": changed, **unread(user)}


@transaction.atomic
def record_subscription(user, data):
    get_user_model().objects.select_for_update().only("pk").get(pk=user.pk)
    digest = hashlib.sha256(
        json.dumps([data["template_key"], data["result"]], ensure_ascii=False).encode()
    ).hexdigest()
    prior = NotificationSubscription.objects.filter(
        user=user, provider=data["provider"], client_event_id=data["client_event_id"]
    ).first()
    if prior:
        if prior.request_digest != digest:
            conflict(Code.IDEMPOTENCY_CONFLICT, "订阅结果标识已用于其他参数")
        return prior, False
    row = NotificationSubscription.objects.create(
        user=user, request_digest=digest, **data
    )
    return row, True


def subscription_data(row):
    return {
        "id": str(row.pk),
        "provider": row.provider,
        "template_key": row.template_key,
        "result": row.result,
        "client_event_id": str(row.client_event_id),
        "recorded_at": row.recorded_at.isoformat(),
        "delivery_status": "not_sent",
    }
