from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.views import APIView
from common.pagination import StandardPagination
from common.response import success
from .models import Product
from .serializers import (
    DraftInput,
    ProductOutput,
    ProductResponse,
    ProductListResponse,
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

    @extend_schema(responses=ProductListResponse)
    def get(self, request):
        rows = products()
        if self.public:
            rows = rows.filter(status=Product.Status.ON_SALE)
        if query := request.query_params.get("q"):
            rows = rows.filter(title__icontains=query[:120])
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
