from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.views import APIView
from cart.api import StrictInput, body, key, HEADER
from catalog.models import Product
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer
from .models import Review
from . import services


class SubmitInput(StrictInput):
    order_item_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(min_length=1, max_length=500, trim_whitespace=True)


class ModerateInput(StrictInput):
    action = serializers.ChoiceField(choices=["approve", "reject", "hide"])
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )

    def validate(self, data):
        if data["action"] in ("reject", "hide") and not data["reason"]:
            raise serializers.ValidationError({"reason": "请填写具体原因"})
        return data


class PublicRow(serializers.Serializer):
    id = serializers.CharField()
    rating = serializers.IntegerField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()
    sku_label = serializers.CharField()
    author_display = serializers.CharField()


class BuyerRow(serializers.Serializer):
    id = serializers.CharField()
    order_item_id = serializers.CharField()
    order_no = serializers.UUIDField()
    product_id = serializers.CharField()
    product_title = serializers.CharField()
    sku_label = serializers.CharField()
    rating = serializers.IntegerField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()
    version = serializers.IntegerField()
    status = serializers.CharField()
    moderation_reason = serializers.CharField()


class OpsRow(BuyerRow):
    quantity = serializers.IntegerField()
    order_status = serializers.CharField()


class Summary(serializers.Serializer):
    count = serializers.IntegerField()
    average = serializers.CharField(allow_null=True)


class Page(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class PublicPage(Page):
    results = PublicRow(many=True)
    rating_summary = Summary()


class BuyerPage(Page):
    results = BuyerRow(many=True)


class OpsPage(Page):
    results = OpsRow(many=True)


class BuyerResponse(EnvelopeSerializer):
    data = BuyerRow()


class OpsResponse(EnvelopeSerializer):
    data = OpsRow()


class PublicListResponse(EnvelopeSerializer):
    data = PublicPage()


class BuyerListResponse(EnvelopeSerializer):
    data = BuyerPage()


class OpsListResponse(EnvelopeSerializer):
    data = OpsPage()


def responses(schema, status=200):
    return {
        status: schema,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }


class Moderator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("reviews.moderate"))


def paged(request, rows, project):
    pager = StandardPagination()
    page = pager.paginate_queryset(rows.order_by("-created_at", "-id"), request)
    return pager.get_paginated_response([project(r) for r in page])


class Submit(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SubmitInput,
        responses=responses(BuyerResponse, 201),
        parameters=[HEADER],
    )
    def post(self, request):
        result = services.write(
            request.user, "submit", key(request), None, body(SubmitInput, request)
        )
        return success(result, http_status=201)


class MineFilter(serializers.Serializer):
    order_no = serializers.UUIDField(required=False)


class OpsFilter(serializers.Serializer):
    status = serializers.ChoiceField(choices=Review.Status.choices, required=False)
    product_id = serializers.IntegerField(
        min_value=1, max_value=2**63 - 1, required=False
    )


PAGING = [OpenApiParameter("page", int), OpenApiParameter("page_size", int)]


class Mine(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[MineFilter, *PAGING], responses=responses(BuyerListResponse)
    )
    def get(self, request):
        form = MineFilter(data=request.query_params)
        form.is_valid(raise_exception=True)
        rows = Review.objects.select_related("order_item__order").filter(
            user=request.user
        )
        if order_no := form.validated_data.get("order_no"):
            rows = rows.filter(order_item__order__order_no=order_no)
        return paged(request, rows, services.buyer_data)


class Public(APIView):
    permission_classes = [AllowAny]

    @extend_schema(parameters=PAGING, responses=responses(PublicListResponse))
    def get(self, request, pk):
        get_object_or_404(Product, pk=pk, status=Product.Status.ON_SALE)
        rows = Review.objects.select_related("order_item").filter(
            product_id=pk, status=Review.Status.APPROVED
        )
        result = paged(request, rows, services.public_data)
        result.data["data"]["rating_summary"] = services.rating_summary(rows)
        return result


class Queue(APIView):
    permission_classes = [Moderator]

    @extend_schema(
        parameters=[OpsFilter, *PAGING], responses=responses(OpsListResponse)
    )
    def get(self, request):
        form = OpsFilter(data=request.query_params)
        form.is_valid(raise_exception=True)
        rows = Review.objects.select_related("order_item__order").filter(
            **form.validated_data
        )
        return paged(request, rows, services.ops_data)


class Moderate(APIView):
    permission_classes = [Moderator]

    @extend_schema(
        request=ModerateInput, responses=responses(OpsResponse), parameters=[HEADER]
    )
    def post(self, request, pk):
        result = services.write(
            request.user, "moderate", key(request), pk, body(ModerateInput, request)
        )
        return success(result)
