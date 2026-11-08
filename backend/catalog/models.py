from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)


class MediaAsset(models.Model):
    file = models.FileField(upload_to="catalog/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ON_SALE = "on_sale", "在售"
        OFF_SALE = "off_sale", "已下架"

    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    cover = models.ForeignKey(
        MediaAsset, null=True, blank=True, on_delete=models.PROTECT
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=Status, default=Status.DRAFT, db_index=True
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [("manage_catalog", "维护商品目录")]


class Sku(models.Model):
    version = models.PositiveIntegerField(default=1)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="skus")
    label = models.CharField(max_length=80)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    available_stock = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "label"], name="catalog_unique_variant"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="catalog_price_nonnegative"
            ),
        ]


class CatalogEvent(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class StockAdjustment(models.Model):
    sku = models.ForeignKey(Sku, on_delete=models.PROTECT, related_name="adjustments")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operator = models.CharField(max_length=150)
    key = models.UUIDField()
    expected_version = models.PositiveIntegerField()
    delta = models.IntegerField()
    reason = models.CharField(max_length=200)
    before = models.PositiveIntegerField()
    after = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "key"], name="catalog_adjustment_key"
            ),
            models.CheckConstraint(
                condition=models.Q(after=models.F("before") + models.F("delta")),
                name="catalog_adjustment_balance",
            ),
        ]
