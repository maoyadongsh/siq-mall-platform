import hashlib
import json

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from common.constants import ErrorCode as Code
from common.exceptions import BusinessError
from orders.models import Order

from .models import (
    ActiveConversation,
    Conversation,
    ReadCursor,
    SupportCommand,
    SupportMessage,
)


def conflict(code, message):
    raise BusinessError(code, message, http_status=409)


def message_data(row):
    return {
        "id": str(row.pk),
        "conversation_id": str(row.conversation_id),
        "conversation_seq": str(row.conversation_seq),
        "sender_role": row.sender_role,
        "client_message_id": str(row.client_message_id),
        "body": row.body,
        "created_at": row.created_at.isoformat(),
    }


def order_summary(order):
    if not order:
        return None
    return {
        "order_no": str(order.order_no),
        "status": order.status,
        "payable_amount": str(order.payable_amount),
        "currency": order.currency,
        "items": [
            {"title": item.snapshot.get("title"), "quantity": item.quantity}
            for item in order.items.order_by("id")
        ],
    }


def authorize(row, user):
    if row.user_id == user.pk:
        return "buyer"
    if not user.has_perm("support.reply"):
        raise Http404
    if row.assigned_agent_id == user.pk or user.has_perm("support.assign"):
        return "agent"
    raise Http404


def locked_conversation(pk, user):
    row = get_object_or_404(Conversation.objects.select_for_update(), pk=pk)
    role = authorize(row, user)
    return row, role


def conversation_data(row, user):
    role = "buyer" if row.user_id == user.pk else "agent"
    cursor = ReadCursor.objects.filter(conversation=row, reader=user).first()
    last_read = cursor.last_seq if cursor else 0
    counterpart_id = row.assigned_agent_id if role == "buyer" else row.user_id
    counterpart = (
        ReadCursor.objects.filter(conversation=row, reader_id=counterpart_id).first()
        if counterpart_id
        else None
    )
    last_message = row.messages.order_by("-conversation_seq", "-id").first()
    agent = row.assigned_agent
    display_name = None
    if agent:
        profile = getattr(agent, "profile", None)
        display_name = (profile.nickname if profile else "") or agent.get_username()
    buyer_profile = getattr(row.user, "profile", None)
    buyer_name = (
        buyer_profile.nickname if buyer_profile else ""
    ) or row.user.get_username()
    return {
        "id": str(row.pk),
        "buyer_display_name": buyer_name,
        "status": row.status,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "close_reason": row.close_reason,
        "assigned_agent_id": (
            str(row.assigned_agent_id) if row.assigned_agent_id else None
        ),
        "assigned_agent_display_name": display_name,
        "last_message": message_data(last_message) if last_message else None,
        "unread_count": row.messages.filter(conversation_seq__gt=last_read)
        .exclude(sender=user)
        .count(),
        "counterpart_read_seq": str(counterpart.last_seq if counterpart else 0),
        "order_summary": order_summary(row.order),
        "can_reply": row.status == "open",
        "can_close": row.status == "open",
    }


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def prior_command(actor, operation, key, parts):
    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    request_digest = digest(parts)
    prior = SupportCommand.objects.filter(
        actor=actor, operation=operation, key=key
    ).first()
    if prior and prior.digest != request_digest:
        conflict(Code.IDEMPOTENCY_CONFLICT, "提交标识已用于其他会话或参数")
    return prior, request_digest


def save_command(actor, operation, key, request_digest, conversation, result):
    SupportCommand.objects.create(
        actor=actor,
        operation=operation,
        key=key,
        digest=request_digest,
        conversation=conversation,
        result=result,
    )


@transaction.atomic
def create_conversation(user, data, action_key):
    prior, request_digest = prior_command(user, "create", action_key, data)
    if prior:
        return prior.result, False
    active = (
        ActiveConversation.objects.select_related("conversation")
        .filter(user=user)
        .first()
    )
    if active:
        return conversation_data(active.conversation, user), False
    order = None
    if data.get("order_no"):
        order = get_object_or_404(Order, user=user, order_no=data["order_no"])
    row = Conversation.objects.create(user=user, order=order)
    ActiveConversation.objects.create(user=user, conversation=row)
    result = conversation_data(row, user)
    save_command(user, "create", action_key, request_digest, row, result)
    return result, True


@transaction.atomic
def assign_conversation(actor, pk, data, action_key):
    prior, request_digest = prior_command(actor, "assign", action_key, [str(pk), data])
    if prior:
        return prior.result
    row = get_object_or_404(Conversation.objects.select_for_update(), pk=pk)
    if row.status != "open":
        conflict(Code.CONVERSATION_CLOSED, "会话已关闭，不能重新分配")
    if row.version != data["expected_version"]:
        conflict(Code.VERSION_CONFLICT, "会话分配已变化，请刷新后核对")
    agent = get_object_or_404(
        get_user_model().objects.filter(is_active=True), pk=data["agent_id"]
    )
    if not agent.has_perm("support.reply"):
        conflict(Code.PERMISSION_DENIED, "目标账号没有客服回复权限")
    if row.assigned_agent_id != agent.pk:
        row.assigned_agent = agent
        row.version += 1
        row.save(update_fields=["assigned_agent", "version", "updated_at"])
    result = conversation_data(row, agent)
    save_command(actor, "assign", action_key, request_digest, row, result)
    return result


@transaction.atomic
def close_conversation(actor, pk, data, action_key):
    prior, request_digest = prior_command(actor, "close", action_key, [str(pk), data])
    if prior:
        return prior.result
    row, _ = locked_conversation(pk, actor)
    if row.status == "open":
        row.status = "closed"
        row.closed_at = timezone.now()
        row.close_reason = data["reason"]
        row.version += 1
        row.save(
            update_fields=[
                "status",
                "closed_at",
                "close_reason",
                "version",
                "updated_at",
            ]
        )
        ActiveConversation.objects.filter(conversation=row).delete()
    result = conversation_data(row, actor)
    save_command(actor, "close", action_key, request_digest, row, result)
    return result


@transaction.atomic
def send_message(actor, pk, data):
    row, role = locked_conversation(pk, actor)
    prior = SupportMessage.objects.filter(
        conversation=row,
        sender=actor,
        client_message_id=data["client_message_id"],
    ).first()
    if prior:
        if prior.body != data["body"]:
            conflict(Code.IDEMPOTENCY_CONFLICT, "消息标识已用于其他正文")
        return message_data(prior), False
    if row.status != "open":
        conflict(Code.CONVERSATION_CLOSED, "会话已关闭，请新开会话")
    row.last_message_seq += 1
    row.save(update_fields=["last_message_seq", "updated_at"])
    message = SupportMessage.objects.create(
        conversation=row,
        conversation_seq=row.last_message_seq,
        sender=actor,
        sender_role=role,
        client_message_id=data["client_message_id"],
        body=data["body"],
    )
    return message_data(message), True


@transaction.atomic
def mark_read(actor, pk, message_id):
    row, _ = locked_conversation(pk, actor)
    message = get_object_or_404(SupportMessage, conversation=row, pk=message_id)
    cursor, _ = ReadCursor.objects.select_for_update().get_or_create(
        conversation=row, reader=actor
    )
    if message.conversation_seq > cursor.last_seq:
        cursor.last_seq = message.conversation_seq
        cursor.last_message = message
        cursor.save(update_fields=["last_seq", "last_message"])
    return {
        "last_seq": str(cursor.last_seq),
        "last_message_id": (
            str(cursor.last_message_id) if cursor.last_message_id else None
        ),
        "unread_count": row.messages.filter(conversation_seq__gt=cursor.last_seq)
        .exclude(sender=actor)
        .count(),
    }


def cursor_token(user, row, direction, message):
    return signing.dumps(
        {
            "user": user.pk,
            "conversation": row.pk,
            "direction": direction,
            "seq": message.conversation_seq,
            "id": message.pk,
        },
        salt="support.message.cursor",
    )


def load_cursor(user, row, token, direction):
    try:
        value = signing.loads(token, salt="support.message.cursor")
    except signing.BadSignature as exc:
        raise BusinessError(Code.INVALID_PARAM, "消息游标无效，请重新加载") from exc
    if (
        value.get("user") != user.pk
        or value.get("conversation") != row.pk
        or value.get("direction") != direction
    ):
        raise BusinessError(Code.INVALID_PARAM, "消息游标与当前会话或方向不一致")
    return value


def history(actor, pk, cursor, limit, direction):
    row = get_object_or_404(Conversation, pk=pk)
    authorize(row, actor)
    rows = SupportMessage.objects.filter(conversation=row)
    if cursor:
        value = load_cursor(actor, row, cursor, direction)
        if direction == "older":
            rows = rows.filter(
                Q(conversation_seq__lt=value["seq"])
                | Q(conversation_seq=value["seq"], pk__lt=value["id"])
            )
        else:
            rows = rows.filter(
                Q(conversation_seq__gt=value["seq"])
                | Q(conversation_seq=value["seq"], pk__gt=value["id"])
            )
    ascending = direction == "newer"
    rows = (
        rows.order_by("conversation_seq", "id")
        if ascending
        else rows.order_by("-conversation_seq", "-id")
    )
    selected = list(rows[: limit + 1])
    has_more = len(selected) > limit
    selected = selected[:limit]
    oldest = selected[-1] if selected else None
    newest = selected[0] if selected else None
    if ascending:
        oldest, newest = selected[0] if selected else None, (
            selected[-1] if selected else None
        )
    next_row = oldest if direction == "older" else newest
    poll_row = newest
    if not ascending:
        selected.reverse()
    return {
        "results": [message_data(message) for message in selected],
        "next_cursor": (
            cursor_token(actor, row, direction, next_row)
            if next_row and (has_more or direction == "newer")
            else None
        ),
        "has_more": has_more,
        "poll_cursor": (
            cursor_token(actor, row, "newer", poll_row) if poll_row else None
        ),
    }
