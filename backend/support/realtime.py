"""客服 WebSocket 的票据、广播与连接辅助。"""

import logging
import secrets

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404

from common.constants import ErrorCode as Code
from common.exceptions import BusinessError

from .models import Conversation
from .services import authorize

logger = logging.getLogger("mall.support")

TICKET_PREFIX = "support:ws:ticket:"


def group_name(conversation_id: int) -> str:
    return f"support_{conversation_id}"


def issue_ticket(user, conversation_id: int, ops: bool = False) -> dict:
    if not settings.SUPPORT_WS_ENABLED:
        raise BusinessError(Code.SERVER_ERROR, "实时客服未启用", http_status=503)
    row = get_object_or_404(Conversation, pk=conversation_id)
    role = authorize(row, user)
    if ops and role != "agent":
        raise Http404
    if not ops and role != "buyer":
        raise Http404
    ticket = secrets.token_urlsafe(32)
    try:
        cache.set(
            f"{TICKET_PREFIX}{ticket}",
            {
                "user_id": user.pk,
                "conversation_id": row.pk,
                "ops": bool(ops),
            },
            timeout=settings.SUPPORT_WS_TICKET_TTL,
        )
    except Exception as exc:  # pragma: no cover - Redis 故障路径
        logger.exception("support websocket ticket cache unavailable")
        raise BusinessError(
            Code.SERVER_ERROR, "实时客服暂不可用，请稍后重试", http_status=503
        ) from exc
    return {
        "ticket": ticket,
        "expires_in": settings.SUPPORT_WS_TICKET_TTL,
        "heartbeat_seconds": settings.SUPPORT_WS_HEARTBEAT_SECONDS,
        "path": f"/ws/support/{row.pk}/",
    }


def consume_ticket(ticket: str | None, conversation_id: int) -> dict | None:
    if not ticket:
        return None
    key = f"{TICKET_PREFIX}{ticket}"
    payload = cache.get(key)
    if not payload:
        return None
    cache.delete(key)
    if payload.get("conversation_id") != conversation_id:
        return None
    return payload


def _group_send(conversation_id: int, message: dict) -> None:
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group_name(conversation_id), message)
    except Exception:  # pragma: no cover - 广播失败不阻断 HTTP 写入
        logger.exception("support websocket broadcast failed")


def broadcast_message(
    conversation_id: int, message: dict, sender_id: int | None = None
) -> None:
    _group_send(
        conversation_id,
        {
            "type": "chat.message",
            "payload": {
                "type": "message",
                "message": message,
                "exclude_user_id": sender_id,
            },
        },
    )


def broadcast_closed(conversation_id: int) -> None:
    _group_send(
        conversation_id,
        {
            "type": "chat.closed",
            "payload": {"type": "closed", "conversation_id": str(conversation_id)},
        },
    )
