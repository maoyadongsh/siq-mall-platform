from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from cart.api import StrictInput
from common.response import success
from common.serializers import EnvelopeSerializer

from .category_services import save_category, tree
from .models import Category
from .views import CanManageCatalog


class CategoryInput(StrictInput):
    parent_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    name = serializers.CharField(min_length=1, max_length=50, trim_whitespace=True)
    sort_order = serializers.IntegerField(
        min_value=-100000, max_value=100000, default=0
    )
    enabled = serializers.BooleanField(default=True)


class CategoryUpdate(CategoryInput):
    expected_version = serializers.IntegerField(min_value=1)


class CategoryData(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    parent_id = serializers.CharField(allow_null=True)
    sort_order = serializers.IntegerField()
    enabled = serializers.BooleanField()
    version = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField(), required=False)


class CategoryResponse(EnvelopeSerializer):
    data = CategoryData()


class CategoryTreeResponse(EnvelopeSerializer):
    data = CategoryData(many=True)


class PublicTree(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="catalog_category_tree", responses=CategoryTreeResponse)
    def get(self, request):
        return success(tree(enabled_only=True))


class ManageTree(APIView):
    permission_classes = [CanManageCatalog]

    @extend_schema(
        operation_id="operator_category_tree", responses=CategoryTreeResponse
    )
    def get(self, request):
        return success(tree())

    @extend_schema(request=CategoryInput, responses={201: CategoryResponse})
    def post(self, request):
        form = CategoryInput(data=request.data)
        form.is_valid(raise_exception=True)
        return success(
            save_category(request.user, form.validated_data), http_status=201
        )


class ManageDetail(APIView):
    permission_classes = [CanManageCatalog]

    @extend_schema(request=CategoryUpdate, responses=CategoryResponse)
    def patch(self, request, pk):
        get_object_or_404(Category, pk=pk)
        form = CategoryUpdate(data=request.data)
        form.is_valid(raise_exception=True)
        return success(save_category(request.user, form.validated_data, pk))
