import uuid
from django.conf import settings
from django.db import models
from catalog.models import Sku


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    version = models.PositiveBigIntegerField(default=0)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey(Sku, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField()
    selected = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "sku"], name="cart_one_sku"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=99),
                name="cart_valid_quantity",
            ),
        ]


class CartOperation(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    operation = models.CharField(max_length=10)
    key = models.UUIDField()
    inputs = models.JSONField()
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "operation", "key"], name="cart_operation_key"
            )
        ]


class Quote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
