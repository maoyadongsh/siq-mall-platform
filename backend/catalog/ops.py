from uuid import UUID
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer
from .maintenance import adjust_stock, edit_product, edit_sku, invalid, upload_image
from .models import MediaAsset, Sku, StockAdjustment
from .serializers import ProductOutput, ProductResponse, SkuOutput, VersionInput
from .views import CanManageCatalog, products


class StrictVersionInput(VersionInput):
    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError("包含不可编辑字段")
        return data


class ProductEdit(StrictVersionInput):
    title = serializers.CharField(max_length=120, required=False)
    category = serializers.CharField(max_length=50, required=False)
    description = serializers.CharField(
        max_length=5000, allow_blank=True, required=False
    )
    cover_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)

    def validate(self, data):
        super().validate(data)
        if len(data) == 1:
            raise serializers.ValidationError("请选择要修改的商品信息")
        return data


class VariantEdit(StrictVersionInput):
    label = serializers.CharField(max_length=80, required=False)
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )
    reason = serializers.CharField(max_length=200)

    def validate(self, data):
        super().validate(data)
        if "price" not in data and "label" not in data:
            raise serializers.ValidationError("请选择要修改的规格信息")
        return data


class AdjustmentInput(StrictVersionInput):
    delta = serializers.IntegerField(min_value=-2147483647, max_value=2147483647)
    reason = serializers.CharField(max_length=200)

    def validate_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("调整数量不能为零")
        return value


class AdjustmentOutput(serializers.ModelSerializer):
    id = serializers.CharField()
    sku_id = serializers.CharField()

    class Meta:
        model = StockAdjustment
        fields = (
            "id",
            "sku_id",
            "operator",
            "delta",
            "before",
            "after",
            "reason",
            "created_at",
        )


class AdjustmentResponse(EnvelopeSerializer):
    data = AdjustmentOutput()


class AdjustmentPage(serializers.Serializer):
    results = AdjustmentOutput(many=True)
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class HistoryResponse(EnvelopeSerializer):
    data = AdjustmentPage()


class VariantResponse(EnvelopeSerializer):
    data = SkuOutput()


class MediaInput(serializers.Serializer):
    file = serializers.FileField()


class AssetOutput(serializers.ModelSerializer):
    asset_id = serializers.CharField(source="id")
    url = serializers.CharField(source="file.url")
    status = serializers.CharField(default="ready")

    class Meta:
        model = MediaAsset
        fields = ("asset_id", "url", "status", "width", "height")


class AssetResponse(EnvelopeSerializer):
    data = AssetOutput()


def validated(schema, request):
    form = schema(data=request.data)
    form.is_valid(raise_exception=True)
    return form.validated_data


class CanUploadMedia(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and (
                request.user.has_perm("catalog.manage_catalog")
                or request.user.has_perm("content.publish")
            )
        )


class Upload(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [CanUploadMedia]

    @extend_schema(request=MediaInput, responses={201: AssetResponse})
    def post(self, request):
        asset = upload_image(request.user, validated(MediaInput, request)["file"])
        return success(AssetOutput(asset).data, http_status=201)


class ProductMaintenance(APIView):
    permission_classes = [CanManageCatalog]

    @extend_schema(operation_id="ops_product_detail", responses=ProductResponse)
    def get(self, request, pk):
        return success(ProductOutput(get_object_or_404(products(), pk=pk)).data)

    @extend_schema(request=ProductEdit, responses=ProductResponse)
    def patch(self, request, pk):
        obj = edit_product(request.user, pk, validated(ProductEdit, request))
        return success(ProductOutput(obj).data)


class VariantMaintenance(APIView):
    permission_classes = [CanManageCatalog]

    @extend_schema(request=VariantEdit, responses=VariantResponse)
    def patch(self, request, pk):
        return success(
            SkuOutput(edit_sku(request.user, pk, validated(VariantEdit, request))).data
        )


class StockHistory(APIView):
    permission_classes = [CanManageCatalog]

    @extend_schema(responses=HistoryResponse)
    def get(self, request, pk):
        sku = get_object_or_404(Sku, pk=pk)
        pager = StandardPagination()
        rows = sku.adjustments.order_by("-id")
        page = pager.paginate_queryset(rows, request)
        return pager.get_paginated_response(AdjustmentOutput(page, many=True).data)

    @extend_schema(
        request=AdjustmentInput,
        responses={201: AdjustmentResponse},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", UUID, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    def post(self, request, pk):
        try:
            key = UUID(request.headers.get("Idempotency-Key", ""))
        except ValueError as exc:
            raise invalid("请提供有效的调整提交标识") from exc
        row = adjust_stock(request.user, pk, key, validated(AdjustmentInput, request))
        return success(AdjustmentOutput(row).data, http_status=201)
