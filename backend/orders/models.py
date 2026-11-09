from uuid import uuid4
from django.conf import settings
from django.db import models
from catalog.models import Sku
from cart.models import Quote


class Order(models.Model):
    order_no = models.UUIDField(default=uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    quote = models.OneToOneField(Quote, on_delete=models.PROTECT)
    intent_id = models.UUIDField()
    coupon_snapshot = models.JSONField(null=True, blank=True)
    address_snapshot = models.JSONField()
    goods_amount = models.DecimalField(max_digits=12, decimal_places=2)
    freight_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="CNY")
    status = models.CharField(max_length=12, default="pending")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    shipment = models.JSONField(null=True)

    @property
    def amounts(self):
        return {
            "goods_amount": str(self.goods_amount),
            "freight_amount": str(self.freight_amount),
            "discount_amount": str(self.discount_amount),
            "payable_amount": str(self.payable_amount),
            "currency": self.currency,
        }

    class Meta:
        permissions = [("fulfill", "处理订单履约")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    goods_amount__gte=0,
                    freight_amount__gte=0,
                    discount_amount__gte=0,
                    payable_amount__gte=0,
                    payable_amount=models.F("goods_amount")
                    + models.F("freight_amount")
                    - models.F("discount_amount"),
                ),
                name="order_amount_balance",
            ),
            models.UniqueConstraint(
                fields=["user", "intent_id"], name="order_per_user_intent"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["user", "created_at"]),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    sku = models.ForeignKey(Sku, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "sku"], name="order_one_line_per_sku"
            )
        ]


class StockMovement(models.Model):
    item = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12)
    available_delta = models.IntegerField()
    reserved_delta = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "kind"], name="order_one_stock_effect"
            )
        ]


class Payment(models.Model):
    pay_no = models.UUIDField(default=uuid4, unique=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    status = models.CharField(max_length=10, default="init")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class Settlement(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT)
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Event(models.Model):
    event_id = models.UUIDField(default=uuid4, unique=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=24)
    reason = models.CharField(max_length=40, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "kind"], name="order_transition_event"
            )
        ]


class OrderActivity(models.Model):
    """Durable first outbox consumer. Later notification consumers track their own receipts."""

    event = models.OneToOneField(Event, on_delete=models.PROTECT)
    received_at = models.DateTimeField(auto_now_add=True)


class Operation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=32)
    key = models.UUIDField()
    digest = models.CharField(max_length=64)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    resource_id = models.UUIDField()
    result = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "operation", "key"], name="order_request_once"
            )
        ]
