from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.views import APIView
from cart.api import StrictInput, body, key, HEADER
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer
from catalog.models import Product
from .models import Template, Coupon, Revision
from .services import command, conflict, coupon_data, template_data
from common.constants import ErrorCode


class Manage(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("promotions.manage"))


class Draft(StrictInput):
    name = serializers.CharField(max_length=80)
    type = serializers.ChoiceField(choices=["fixed", "percentage"])
    threshold_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0
    )
    reduction_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        allow_null=True,
        required=False,
        default=None,
    )
    discount_bps = serializers.IntegerField(
        min_value=1, max_value=10000, allow_null=True, required=False, default=None
    )
    cap_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        allow_null=True,
        required=False,
        default=None,
    )
    scope = serializers.ChoiceField(choices=["all", "products"])
    product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2**63 - 1), max_length=500
    )
    total = serializers.IntegerField(min_value=1, max_value=2147483647)
    per_user_limit = serializers.IntegerField(min_value=1, max_value=32767)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    claim_start_at = serializers.DateTimeField()
    claim_end_at = serializers.DateTimeField()

    def validate(self, data):
        if (
            not data["start_at"]
            <= data["claim_start_at"]
            < data["claim_end_at"]
            <= data["end_at"]
        ):
            raise serializers.ValidationError("领取时段必须落在使用有效期内")
        fixed = data["type"] == "fixed"
        if fixed and (
            not data["reduction_amount"] or data["discount_bps"] or data["cap_amount"]
        ):
            raise serializers.ValidationError("满减券仅填写固定减免额")
        if not fixed and (
            data["reduction_amount"]
            or not data["discount_bps"]
            or not data["cap_amount"]
        ):
            raise serializers.ValidationError("比例券须指定减免比例与封顶金额")
        ids = data["product_ids"]
        if (data["scope"] == "all") != (not ids) or Product.objects.filter(
            pk__in=ids
        ).count() != len(ids):
            raise serializers.ValidationError("请核对适用商品清单")
        if data["per_user_limit"] > data["total"]:
            raise serializers.ValidationError("限领数不能超过总量")
        return data


class Action(StrictInput):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=200)


class RuleData(serializers.Serializer):
    id = serializers.CharField()
    template_id = serializers.CharField()
    template_version = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    threshold_amount = serializers.CharField()
    reduction_amount = serializers.CharField(allow_null=True)
    discount_bps = serializers.IntegerField(allow_null=True)
    cap_amount = serializers.CharField(allow_null=True)
    scope = serializers.CharField()
    product_ids = serializers.ListField(child=serializers.CharField())
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()


class TemplateData(RuleData):
    version = serializers.IntegerField()
    issued = serializers.IntegerField()
    total = serializers.IntegerField()
    per_user_limit = serializers.IntegerField()
    claim_start_at = serializers.DateTimeField()
    claim_end_at = serializers.DateTimeField()
    reserved = serializers.IntegerField(required=False)
    used = serializers.IntegerField(required=False)


class CouponData(RuleData):
    order_no = serializers.UUIDField(allow_null=True)
    serial_no = serializers.UUIDField()


class TemplateResponse(EnvelopeSerializer):
    data = TemplateData()


class CouponResponse(EnvelopeSerializer):
    data = CouponData()


class Page(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class TemplatesPage(Page):
    results = TemplateData(many=True)


class WalletPage(Page):
    results = CouponData(many=True)


class TemplateListResponse(EnvelopeSerializer):
    data = TemplatesPage()


class WalletResponse(EnvelopeSerializer):
    data = WalletPage()


def response(schema, status=200):
    return {
        status: schema,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }


class Templates(APIView):
    permission_classes = [AllowAny]
    ops = False

    @extend_schema(responses=response(TemplateListResponse))
    def get(self, request):
        rows = Template.objects.prefetch_related("products")
        now = timezone.now()
        if self.ops:
            rows = rows.annotate(
                reserved=Count("coupon", filter=Q(coupon__status="reserved")),
                used=Count("coupon", filter=Q(coupon__status="used")),
            )
        else:
            rows = rows.filter(
                status="active",
                claim_start_at__lte=now,
                claim_end_at__gt=now,
                issued__lt=F("total"),
            )
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-pk"), request)
        return pager.get_paginated_response(
            [
                {
                    **template_data(t),
                    **({"reserved": t.reserved, "used": t.used} if self.ops else {}),
                }
                for t in page
            ]
        )


@extend_schema_view(get=extend_schema(operation_id="ops_coupon_list"))
class OpsTemplates(Templates):
    ops = True
    permission_classes = [Manage]

    @extend_schema(request=Draft, responses=response(TemplateResponse, 201))
    @transaction.atomic
    def post(self, request):
        data = body(Draft, request)
        ids = data.pop("product_ids")
        t = Template.objects.create(**data)
        t.products.set(ids)
        Revision.objects.create(
            template=t,
            version=t.version,
            actor=request.user,
            action="create",
            snapshot=template_data(t),
        )
        return success(template_data(t), http_status=201)


class DraftPatch(Draft):
    expected_version = serializers.IntegerField(min_value=1)


class OpsDetail(APIView):
    permission_classes = [Manage]

    @extend_schema(responses=response(TemplateResponse))
    def get(self, request, pk):
        return success(template_data(get_object_or_404(Template, pk=pk)))

    @extend_schema(request=DraftPatch, responses=response(TemplateResponse))
    @transaction.atomic
    def patch(self, request, pk):
        t = get_object_or_404(Template.objects.select_for_update(), pk=pk)
        if t.status != "draft":
            conflict("仅草稿可编辑")
        current = template_data(t)
        if not isinstance(request.data, dict):
            raise serializers.ValidationError({"detail": "需要JSON对象"})
        merged = {k: current[k] for k in Draft().fields}
        form = DraftPatch(data={**merged, **request.data})
        form.is_valid(raise_exception=True)
        data = form.validated_data
        if data.pop("expected_version") != t.version:
            conflict("版本已变化，请刷新", ErrorCode.VERSION_CONFLICT)
        ids = data.pop("product_ids")
        for k, v in data.items():
            setattr(t, k, v)
        t.version += 1
        t.save()
        t.products.set(ids)
        Revision.objects.create(
            template=t,
            version=t.version,
            actor=request.user,
            action="edit",
            snapshot=template_data(t),
        )
        return success(template_data(t))


class Lifecycle(APIView):
    permission_classes = [Manage]
    operation = "publish"

    @extend_schema(
        request=Action, responses=response(TemplateResponse), parameters=[HEADER]
    )
    def post(self, request, pk):
        return success(
            command(
                request.user, pk, self.operation, key(request), body(Action, request)
            )
        )


class Claim(APIView):
    def check_throttles(self, request):
        from redis.exceptions import (
            ConnectionError as RedisConnectionError,
            TimeoutError as RedisTimeoutError,
        )
        from django_redis.exceptions import ConnectionInterrupted
        from common.exceptions import BusinessError

        try:
            super().check_throttles(request)
        except (RedisConnectionError, RedisTimeoutError, ConnectionInterrupted) as exc:
            raise BusinessError(
                ErrorCode.COUPON_NOT_CLAIMABLE,
                "领取服务暂时繁忙，请稍后用原请求重试",
                http_status=503,
            ) from exc

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=StrictInput,
        responses={**response(CouponResponse, 201), 503: ErrorResponseSerializer},
        parameters=[HEADER],
    )
    def post(self, request, pk):
        return success(
            command(
                request.user, pk, "claim", key(request), body(StrictInput, request)
            ),
            http_status=201,
        )


class Wallet(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=response(WalletResponse))
    def get(self, request):
        now = timezone.now()
        rows = Coupon.objects.filter(user=request.user).select_related("order")
        state = request.query_params.get("status")
        if state == "expired":
            rows = rows.filter(
                Q(status="expired") | Q(status="unused", end_at__lte=now)
            )
        elif state == "unused":
            rows = rows.filter(status="unused", end_at__gt=now)
        elif state in ("used", "reserved"):
            rows = rows.filter(status=state)
        elif state:
            raise serializers.ValidationError({"status": "无效状态"})
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-id"), request)
        return pager.get_paginated_response([coupon_data(c, now) for c in page])
