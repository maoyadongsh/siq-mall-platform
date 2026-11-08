from rest_framework import serializers
from common.serializers import EnvelopeSerializer
from .models import Product, Sku


class SkuInput(serializers.Serializer):
    label = serializers.CharField(max_length=80)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    available_stock = serializers.IntegerField(min_value=0, max_value=2147483647)


class DraftInput(serializers.Serializer):
    category = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(
        max_length=5000, allow_blank=True, required=False
    )
    skus = SkuInput(many=True, allow_empty=False, max_length=100)

    def validate_skus(self, rows):
        labels = [row["label"].casefold() for row in rows]
        if len(labels) != len(set(labels)):
            raise serializers.ValidationError("规格名称不能重复")
        return rows


class SkuOutput(serializers.ModelSerializer):
    id = serializers.CharField()

    class Meta:
        model = Sku
        fields = ("id", "label", "price", "available_stock")


class ProductOutput(serializers.ModelSerializer):
    id = serializers.CharField()
    category = serializers.CharField(source="category.name")
    skus = SkuOutput(many=True)
    currency = serializers.CharField(default="CNY")

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "category",
            "description",
            "status",
            "version",
            "skus",
            "currency",
        )


class VersionInput(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class ProductResponse(EnvelopeSerializer):
    data = ProductOutput()


class ProductPage(serializers.Serializer):
    results = ProductOutput(many=True)
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class ProductListResponse(EnvelopeSerializer):
    data = ProductPage()
