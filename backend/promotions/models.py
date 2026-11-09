from uuid import uuid4
from django.conf import settings
from django.db import models
from catalog.models import Product
from orders.models import Order


class Template(models.Model):
    name = models.CharField(max_length=80)
    type = models.CharField(
        max_length=12, choices=[("fixed", "满减"), ("percentage", "比例减免")]
    )
    threshold_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reduction_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    discount_bps = models.PositiveSmallIntegerField(null=True)
    cap_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    scope = models.CharField(
        max_length=10, choices=[("all", "全场"), ("products", "指定商品")]
    )
    products = models.ManyToManyField(Product, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    claim_start_at = models.DateTimeField()
    claim_end_at = models.DateTimeField()
    total = models.PositiveIntegerField()
    issued = models.PositiveIntegerField(default=0)
    per_user_limit = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, default="draft")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [("manage", "管理优惠券")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    issued__lte=models.F("total"),
                    per_user_limit__gte=1,
                    per_user_limit__lte=models.F("total"),
                ),
                name="coupon_within_supply",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    start_at__lte=models.F("claim_start_at"),
                    claim_start_at__lt=models.F("claim_end_at"),
                    claim_end_at__lte=models.F("end_at"),
                ),
                name="coupon_valid_windows",
            ),
        ]


class Coupon(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    template = models.ForeignKey(Template, on_delete=models.PROTECT)
    serial_no = models.UUIDField(default=uuid4, unique=True)
    claim_index = models.PositiveSmallIntegerField()
    terms = models.JSONField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=12, default="unused")
    order = models.OneToOneField(Order, null=True, on_delete=models.PROTECT)
    reserved_at = models.DateTimeField(null=True)
    used_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "user", "claim_index"], name="coupon_claim_slot"
            )
        ]
        indexes = [models.Index(fields=["user", "status", "end_at"])]


class Receipt(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=16)
    key = models.UUIDField()
    template = models.ForeignKey(Template, on_delete=models.PROTECT)
    inputs = models.JSONField()
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation", "key"], name="coupon_command_key"
            )
        ]


class Revision(models.Model):
    template = models.ForeignKey(Template, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=16)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version"], name="coupon_revision_once"
            )
        ]
