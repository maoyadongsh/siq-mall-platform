from decimal import Decimal, InvalidOperation

from django.db.models import Min
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.views import APIView

from common.pagination import StandardPagination
from common.response import success

from .category_services import descendants
from .models import Category, Product
from .serializers import (
    DraftInput,
    ProductListResponse,
    ProductOutput,
    ProductResponse,
    VersionInput,
)
from .services import change_status, create_draft


class CanManageCatalog(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("catalog.manage_catalog"))


def products():
    return (
        Product.objects.select_related("category", "cover")
        .prefetch_related("skus")
        .order_by("-id")
    )


class PublicProducts(APIView):
    permission_classes = [AllowAny]
    public = True

    @extend_schema(
        responses=ProductListResponse,
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("category", int),
            OpenApiParameter("min_price", str),
            OpenApiParameter("max_price", str),
            OpenApiParameter(
                "sort", str, enum=["newest", "price_asc", "price_desc", "title"]
            ),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        rows = products().annotate(min_price=Min("skus__price"))
        if self.public:
            rows = rows.filter(status=Product.Status.ON_SALE)
        if query := request.query_params.get("q"):
            rows = rows.filter(title__icontains=query[:120])
        if category_id := request.query_params.get("category"):
            try:
                category = get_object_or_404(
                    Category, pk=int(category_id), enabled=True
                )
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"category": "请输入有效分类"}
                ) from exc
            rows = rows.filter(category_id__in=descendants(category))
        prices = {}
        for field in ("min_price", "max_price"):
            if value := request.query_params.get(field):
                try:
                    prices[field] = Decimal(value)
                    if prices[field] < 0:
                        raise InvalidOperation
                except InvalidOperation as exc:
                    raise serializers.ValidationError(
                        {field: "请输入非负金额"}
                    ) from exc
                rows = rows.filter(
                    **{
                        f"min_price__{'gte' if field == 'min_price' else 'lte'}": prices[
                            field
                        ]
                    }
                )
        if prices.get("min_price") is not None and prices.get("max_price") is not None:
            if prices["min_price"] > prices["max_price"]:
                raise serializers.ValidationError({"max_price": "价格上限不能小于下限"})
        sort = request.query_params.get("sort", "newest")
        ordering = {
            "newest": ["-id"],
            "price_asc": ["min_price", "id"],
            "price_desc": ["-min_price", "-id"],
            "title": ["title", "-id"],
        }.get(sort)
        if ordering is None:
            raise serializers.ValidationError({"sort": "不支持的排序方式"})
        rows = rows.order_by(*ordering)
        pager = StandardPagination()
        return pager.get_paginated_response(
            ProductOutput(pager.paginate_queryset(rows, request), many=True).data
        )


class PublicDetail(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="catalog_product_detail", responses=ProductResponse)
    def get(self, request, pk):
        obj = get_object_or_404(products(), pk=pk, status=Product.Status.ON_SALE)
        return success(ProductOutput(obj).data)


class ManageProducts(PublicProducts):
    permission_classes = [CanManageCatalog]
    public = False

    @extend_schema(request=DraftInput, responses={201: ProductResponse})
    def post(self, request):
        form = DraftInput(data=request.data)
        form.is_valid(raise_exception=True)
        return success(
            ProductOutput(create_draft(request.user, form.validated_data)).data,
            http_status=201,
        )


class Publication(APIView):
    permission_classes = [CanManageCatalog]
    publish = True

    @extend_schema(request=VersionInput, responses=ProductResponse)
    def post(self, request, pk):
        form = VersionInput(data=request.data)
        form.is_valid(raise_exception=True)
        obj = change_status(
            request.user, pk, form.validated_data["expected_version"], self.publish
        )
        return success(ProductOutput(obj).data)
