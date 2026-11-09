from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from cart.api import StrictInput, HEADER, key, body
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer
from . import services as svc
from .models import Order, Payment, Operation, OrderActivity


def responses(schema, status=200):
    return {
        status: schema,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }


class Create(StrictInput):
    intent_id = serializers.UUIDField()
    quote_id = serializers.UUIDField()


class Cancel(StrictInput):
    reason = serializers.ChoiceField(choices=["user_changed_mind", "other"])


class Pay(StrictInput):
    order_no = serializers.UUIDField()


class Outcome(StrictInput):
    outcome = serializers.ChoiceField(choices=["success", "failed"])


class Ship(StrictInput):
    expected_version = serializers.IntegerField(min_value=1)
    carrier = serializers.CharField(max_length=50)
    tracking_no = serializers.CharField(max_length=100)


class OrderSummary(serializers.Serializer):
    order_no = serializers.UUIDField()
    status = serializers.CharField()
    version = serializers.IntegerField()
    goods_amount = serializers.CharField()
    freight_amount = serializers.CharField()
    discount_amount = serializers.CharField()
    payable_amount = serializers.CharField()
    currency = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class PayData(serializers.Serializer):
    pay_no = serializers.UUIDField()
    order_no = serializers.UUIDField()
    status = serializers.CharField()
    order_status = serializers.CharField()
    mode = serializers.CharField()
    amount = serializers.CharField()
    expires_at = serializers.DateTimeField()


class OrderDetailData(OrderSummary):
    items = serializers.ListField(child=serializers.DictField())
    address_snapshot = serializers.DictField()
    events = serializers.ListField(child=serializers.DictField())
    payment_summary = PayData(allow_null=True)
    shipment = serializers.DictField(allow_null=True)
    coupon_snapshot = serializers.DictField(allow_null=True)


class OrderResponse(EnvelopeSerializer):
    data = OrderDetailData()


class PaymentResponse(EnvelopeSerializer):
    data = PayData()


class PageData(serializers.Serializer):
    count = serializers.IntegerField()
    page_size = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = OrderSummary(many=True)


class PageResponse(EnvelopeSerializer):
    data = PageData()


class OperationData(serializers.Serializer):
    status = serializers.CharField()
    resource_type = serializers.CharField()
    resource_id = serializers.UUIDField()
    retry_after_seconds = serializers.IntegerField()


class OpResponse(EnvelopeSerializer):
    data = OperationData()


class Filter(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["pending", "paid", "shipped", "completed", "canceled"], required=False
    )
    created_before = serializers.DateTimeField(required=False)
    created_after = serializers.DateTimeField(required=False)
    order_no = serializers.UUIDField(required=False)


class Fulfill(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("orders.fulfill"))


class Demo(BasePermission):
    message = "该环境未启用模拟支付"

    def has_permission(self, request, view):
        return settings.DEMO_PAYMENT_ENABLED


def command(request, operation, schema, func, status=200, target=None):
    data = body(schema, request)
    result = svc.execute(
        request.user,
        operation,
        key(request),
        {"target": target, **data},
        lambda: func(data),
    )
    return success(result, http_status=status)


class OrderList(APIView):
    permission_classes = [IsAuthenticated]
    ops = False

    @extend_schema(
        responses=responses(PageResponse),
        parameters=[
            Filter,
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        rows = (
            Order.objects.all() if self.ops else Order.objects.filter(user=request.user)
        )
        form = Filter(data=request.query_params)
        form.is_valid(raise_exception=True)
        for field, value in form.validated_data.items():
            lookup = {
                "created_before": "created_at__lte",
                "created_after": "created_at__gte",
            }.get(field, field)
            rows = rows.filter(**{lookup: value})
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-created_at", "-id"), request)
        return pager.get_paginated_response([svc.summary(o, self.ops) for o in page])


@extend_schema_view(get=extend_schema(operation_id="operator_order_list"))
class OpsList(OrderList):
    ops = True
    permission_classes = [Fulfill]


@extend_schema_view(get=extend_schema(operation_id="buyer_order_list"))
class BuyerList(OrderList):
    @extend_schema(
        request=Create, responses=responses(OrderResponse, 201), parameters=[HEADER]
    )
    def post(self, request):
        return command(
            request, "order.create", Create, lambda d: svc.place(request.user, d), 201
        )


class Detail(APIView):
    permission_classes = [IsAuthenticated]
    ops = False

    @extend_schema(responses=responses(OrderResponse))
    def get(self, request, no):
        rows = (
            Order.objects.all() if self.ops else Order.objects.filter(user=request.user)
        )
        return success(svc.detail(get_object_or_404(rows, order_no=no), self.ops))


class OpsDetail(Detail):
    ops = True
    permission_classes = [Fulfill]


class Intent(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=responses(OrderResponse))
    def get(self, request, intent):
        return success(
            svc.detail(get_object_or_404(Order, user=request.user, intent_id=intent))
        )


class Lookup(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=responses(OpResponse))
    def get(self, request, operation, token):
        row = get_object_or_404(
            Operation, user=request.user, key=token, operation=operation
        )
        return success(
            {
                "status": "succeeded",
                "resource_type": (
                    "payment" if operation.startswith("payment.") else "order"
                ),
                "resource_id": str(row.resource_id),
                "retry_after_seconds": 0,
            }
        )


class CancelOrder(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=Cancel, responses=responses(OrderResponse), parameters=[HEADER]
    )
    def post(self, request, no):
        return command(
            request,
            "order.cancel",
            Cancel,
            lambda d: svc.cancel(request.user, no, d),
            target=no,
        )


class Receive(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=StrictInput, responses=responses(OrderResponse), parameters=[HEADER]
    )
    def post(self, request, no):
        return command(
            request,
            "order.receive",
            StrictInput,
            lambda _: svc.receive(request.user, no),
            target=no,
        )


class Shipment(APIView):
    permission_classes = [Fulfill]

    @extend_schema(
        request=Ship, responses=responses(OrderResponse), parameters=[HEADER]
    )
    def post(self, request, no):
        return command(
            request,
            "order.ship",
            Ship,
            lambda d: svc.ship(request.user, no, d),
            target=no,
        )


class Payments(APIView):
    permission_classes = [IsAuthenticated, Demo]

    @extend_schema(
        request=Pay, responses=responses(PaymentResponse, 201), parameters=[HEADER]
    )
    def post(self, request):
        return command(
            request,
            "payment.create",
            Pay,
            lambda d: svc.init_payment(request.user, d),
            201,
        )


class Attempt(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=responses(PaymentResponse))
    def get(self, request, no):
        p = get_object_or_404(
            Payment.objects.select_related("order"), order__user=request.user, pay_no=no
        )
        return success(svc.payment_data(p, p.order))


class Simulate(APIView):
    permission_classes = [IsAuthenticated, Demo]

    @extend_schema(
        request=Outcome, responses=responses(PaymentResponse), parameters=[HEADER]
    )
    def post(self, request, no):
        return command(
            request,
            "payment.simulate",
            Outcome,
            lambda d: svc.simulate(request.user, no, d),
            target=no,
        )


class ActivityRow(serializers.Serializer):
    order_no = serializers.UUIDField(source="event.order.order_no")
    type = serializers.CharField(source="event.kind")
    occurred_at = serializers.DateTimeField(source="event.occurred_at")


class ActivityResponse(EnvelopeSerializer):
    data = ActivityRow(many=True)


class ActivityFeed(APIView):
    permission_classes = [Fulfill]

    @extend_schema(responses=responses(ActivityResponse))
    def get(self, request):
        rows = OrderActivity.objects.select_related("event__order").order_by(
            "-event__occurred_at", "-pk"
        )[:20]
        return success(ActivityRow(rows, many=True).data)
