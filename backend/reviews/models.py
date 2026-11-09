from django.conf import settings
from django.db import models
from catalog.models import Product
from orders.models import OrderItem


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已公开"
        REJECTED = "rejected", "未通过"
        HIDDEN = "hidden", "已隐藏"

    order_item = models.OneToOneField(OrderItem, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_reviews",
    )
    rating = models.PositiveSmallIntegerField()
    content = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    version = models.PositiveIntegerField(default=1)
    moderation_reason = models.CharField(max_length=200, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
        related_name="moderated_reviews",
    )
    moderated_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("moderate", "审核商品评价")]
        indexes = [
            models.Index(fields=["product", "status", "created_at", "id"]),
            models.Index(fields=["user", "created_at", "id"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_star_bounds",
            )
        ]


class ReviewAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=12)
    key = models.UUIDField()
    digest = models.CharField(max_length=64)
    review = models.ForeignKey(Review, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    reason = models.CharField(max_length=200, blank=True)
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation", "key"], name="review_command_once"
            ),
            models.UniqueConstraint(
                fields=["review", "version"], name="review_revision_once"
            ),
        ]
