from uuid import uuid4

from django.conf import settings
from django.db import models


class ContentAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("publish", "发布CMS内容与通知模板")]


class Content(models.Model):
    kind = models.CharField(max_length=16)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=12, default="draft")
    published_revision = models.ForeignKey(
        "content.ContentRevision",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="published_for",
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["kind", "status", "id"])]


class ContentRevision(models.Model):
    content = models.ForeignKey(
        Content, on_delete=models.PROTECT, related_name="revisions"
    )
    revision_no = models.PositiveIntegerField()
    title = models.CharField(max_length=120)
    blocks = models.JSONField(default=list)
    platforms = models.JSONField(default=list)
    sort_order = models.IntegerField(default=0)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    notify_inbox = models.BooleanField(default=False)
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content", "revision_no"], name="content_revision_once"
            )
        ]
        indexes = [models.Index(fields=["start_at", "end_at", "id"])]


class ContentEvent(models.Model):
    event_id = models.UUIDField(default=uuid4, unique=True)
    revision = models.OneToOneField(ContentRevision, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40, default="cms.announcement_published")
    occurred_at = models.DateTimeField(auto_now_add=True)


class ContentAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    content = models.ForeignKey(
        Content, on_delete=models.PROTECT, related_name="actions"
    )
    revision = models.ForeignKey(ContentRevision, null=True, on_delete=models.PROTECT)
    operation = models.CharField(max_length=16)
    key = models.UUIDField(null=True, blank=True)
    digest = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    snapshot = models.JSONField(default=dict)
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation", "key"], name="content_command_once"
            )
        ]
        indexes = [models.Index(fields=["content", "created_at", "id"])]
