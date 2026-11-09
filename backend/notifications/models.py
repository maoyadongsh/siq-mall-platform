from uuid import uuid4

from django.conf import settings
from django.db import models


class NotificationTemplate(models.Model):
    event_type = models.CharField(max_length=40)
    channel = models.CharField(max_length=20, default="inbox")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=1000)
    variables = models.JSONField(default=list)
    enabled = models.BooleanField(default=False)
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "channel", "version"],
                name="notification_template_version",
            )
        ]
        indexes = [models.Index(fields=["event_type", "channel", "version"])]


class NotificationTemplatePointer(models.Model):
    event_type = models.CharField(max_length=40)
    channel = models.CharField(max_length=20, default="inbox")
    template = models.ForeignKey(NotificationTemplate, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "channel"], name="notification_active_template"
            )
        ]


class NotificationTemplateAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=16)
    key = models.UUIDField()
    digest = models.CharField(max_length=64)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.PROTECT)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation", "key"], name="notification_template_once"
            )
        ]


class NotificationSequence(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_seq = models.PositiveBigIntegerField(default=0)


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    recipient_seq = models.PositiveBigIntegerField()
    event_id = models.UUIDField()
    type = models.CharField(max_length=16)
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=1000)
    target_type = models.CharField(max_length=24)
    target_id = models.CharField(max_length=64)
    read_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event_id", "type"], name="notification_event_once"
            ),
            models.UniqueConstraint(
                fields=["user", "recipient_seq"], name="notification_recipient_seq"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "read_at", "recipient_seq"]),
            models.Index(fields=["user", "type", "recipient_seq", "id"]),
        ]


class NotificationConsumption(models.Model):
    event_id = models.UUIDField()
    consumer = models.CharField(max_length=64)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "consumer"], name="notification_consumer_once"
            )
        ]


class NotificationSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=24)
    template_key = models.CharField(max_length=100)
    result = models.CharField(max_length=16)
    client_event_id = models.UUIDField(default=uuid4)
    request_digest = models.CharField(max_length=64)
    delivery_reference = models.CharField(max_length=100, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "client_event_id"],
                name="notification_subscription_once",
            )
        ]
