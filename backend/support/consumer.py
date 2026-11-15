"""客服 WebSocket 消费者：服务端只推送，发送消息仍走 HTTP 幂等接口。"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404

from . import realtime
from .models import Conversation
from .services import authorize


def _origin_allowed(scope) -> bool:
    if settings.DEBUG:
        return True
    headers = dict(scope.get("headers") or [])
    origin = headers.get(b"origin")
    if not origin:
        return True
    return origin.decode("latin-1") in settings.CORS_ALLOWED_ORIGINS


class SupportConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["pk"])
        self.group = realtime.group_name(self.conversation_id)
        self.joined = False
        if not settings.SUPPORT_WS_ENABLED:
            await self.close(code=4403)
            return

        protocols = list(self.scope.get("subprotocols") or [])
        if not protocols:
            headers = dict(self.scope.get("headers") or [])
            raw = headers.get(b"sec-websocket-protocol", b"").decode("latin-1")
            protocols = [item.strip() for item in raw.split(",") if item.strip()]
        ticket = None
        for item in protocols:
            if item.startswith("support.ticket."):
                ticket = item[len("support.ticket.") :]
                break
        payload = await database_sync_to_async(realtime.consume_ticket)(
            ticket, self.conversation_id
        )
        if not payload:
            await self.close(code=4401)
            return
        if not _origin_allowed(self.scope):
            await self.close(code=4403)
            return

        user = await database_sync_to_async(
            get_user_model().objects.filter(pk=payload["user_id"], is_active=True).first
        )()
        if not user:
            await self.close(code=4401)
            return
        self.user_id = user.pk
        row = await database_sync_to_async(
            Conversation.objects.filter(pk=self.conversation_id).first
        )()
        if not row:
            await self.close(code=4404)
            return
        try:
            role = await database_sync_to_async(authorize)(row, user)
        except Http404:
            await self.close(code=4403)
            return
        expected = "agent" if payload.get("ops") else "buyer"
        if role != expected:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group, self.channel_name)
        self.joined = True
        await self.accept()
        await self.send_json(
            {
                "type": "ready",
                "conversation_id": str(self.conversation_id),
                "role": role,
            }
        )

    async def disconnect(self, code):
        if getattr(self, "joined", False):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})
            return
        await self.send_json(
            {"type": "error", "code": "unsupported", "message": "仅支持心跳消息"}
        )

    async def chat_message(self, event):
        payload = event["payload"]
        if payload.get("exclude_user_id") == self.user_id:
            return
        await self.send_json({"type": "message", "message": payload["message"]})

    async def chat_closed(self, event):
        await self.send_json(event["payload"])
