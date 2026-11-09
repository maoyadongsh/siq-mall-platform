from uuid import uuid4

from django.conf import settings
from django.db import models

from orders.models import Order


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_conversations",
    )
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, default="open")
    last_message_seq = models.PositiveBigIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        permissions = [
            ("reply", "回复已授权客服会话"),
            ("assign", "分配客服会话"),
        ]
        indexes = [
            models.Index(fields=["user", "updated_at", "id"]),
            models.Index(fields=["assigned_agent", "status", "updated_at", "id"]),
        ]


class ActiveConversation(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    conversation = models.OneToOneField(Conversation, on_delete=models.PROTECT)


class SupportMessage(models.Model):
    notification_event_id = models.UUIDField(default=uuid4, unique=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="messages"
    )
    conversation_seq = models.PositiveBigIntegerField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sender_role = models.CharField(max_length=10)
    client_message_id = models.UUIDField()
    body = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sender", "client_message_id"],
                name="support_client_message_once",
            ),
            models.UniqueConstraint(
                fields=["conversation", "conversation_seq"],
                name="support_conversation_seq",
            ),
        ]
        indexes = [models.Index(fields=["conversation", "conversation_seq", "id"])]


class ReadCursor(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    reader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_seq = models.PositiveBigIntegerField(default=0)
    last_message = models.ForeignKey(
        SupportMessage, null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "reader"], name="support_reader_once"
            )
        ]


class SupportCommand(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=16)
    key = models.UUIDField()
    digest = models.CharField(max_length=64)
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True, on_delete=models.PROTECT
    )
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation", "key"], name="support_command_once"
            )
        ]
