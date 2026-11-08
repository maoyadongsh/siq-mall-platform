from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ON_SALE = "on_sale", "在售"
        OFF_SALE = "off_sale", "已下架"

    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=Status, default=Status.DRAFT, db_index=True
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [("manage_catalog", "维护商品目录")]


class Sku(models.Model):
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
