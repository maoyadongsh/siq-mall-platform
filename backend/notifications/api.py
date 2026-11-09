from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from cart.api import HEADER, StrictInput, body, key
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer

from . import services as svc
from .models import NotificationTemplate


def responses(schema, status=200):
    return {
        status: schema,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }


class CanPublishContent(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("content.publish"))


class Notice(serializers.Serializer):
    id = serializers.CharField()
    recipient_seq = serializers.CharField()
    type = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    created_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)


class NoticePage(serializers.Serializer):
    results = Notice(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()
    read_watermark = serializers.CharField()


class NoticePageResponse(EnvelopeSerializer):
    data = NoticePage()


class ByType(serializers.Serializer):
    order = serializers.IntegerField()
    support = serializers.IntegerField()
    system = serializers.IntegerField()


class Unread(serializers.Serializer):
    total = serializers.IntegerField()
    by_type = ByType()


class UnreadResponse(EnvelopeSerializer):
    data = Unread()


class ReadInput(StrictInput):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        max_length=100,
        allow_empty=False,
        required=False,
    )
    watermark = serializers.CharField(required=False)
    type = serializers.ChoiceField(choices=svc.NOTICE_TYPES, required=False)

    def validate(self, data):
        if ("ids" in data) == ("watermark" in data):
            raise serializers.ValidationError("ids与watermark必须且只能提供一项")
        if "ids" in data and "type" in data:
            raise serializers.ValidationError("按ID已读时不能同时传分类")
        return data


class ReadResult(Unread):
    updated_count = serializers.IntegerField()


class ReadResponse(EnvelopeSerializer):
    data = ReadResult()


class SubscriptionInput(StrictInput):
    provider = serializers.ChoiceField(choices=["wechat_mini"])
    template_key = serializers.RegexField(r"^[A-Za-z0-9_.:-]{1,100}$")
    result = serializers.ChoiceField(
        choices=["accept", "reject", "failed", "unavailable"]
    )
    client_event_id = serializers.UUIDField()


class SubscriptionData(serializers.Serializer):
    id = serializers.CharField()
    provider = serializers.CharField()
    template_key = serializers.CharField()
    result = serializers.CharField()
    client_event_id = serializers.UUIDField()
    recorded_at = serializers.DateTimeField()
    delivery_status = serializers.CharField()


class SubscriptionResponse(EnvelopeSerializer):
    data = SubscriptionData()


class NoticeList(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=responses(NoticePageResponse),
        parameters=[
            OpenApiParameter("type", str, enum=list(svc.NOTICE_TYPES)),
            OpenApiParameter("cursor", str),
            OpenApiParameter("limit", int),
        ],
    )
    def get(self, request):
        notice_type = request.query_params.get("type", "")
        if notice_type and notice_type not in svc.NOTICE_TYPES:
            raise serializers.ValidationError({"type": "不支持的消息分类"})
        try:
            limit = min(int(request.query_params.get("limit", 20)), 100)
            if limit < 1:
                raise ValueError
        except ValueError as exc:
            raise serializers.ValidationError({"limit": "请输入1–100的整数"}) from exc
        return success(
            svc.page(
                request.user,
                notice_type,
                request.query_params.get("cursor"),
                limit,
            )
        )


class UnreadCount(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=responses(UnreadResponse))
    def get(self, request):
        return success(svc.unread(request.user))


class MarkRead(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ReadInput, responses=responses(ReadResponse))
    def post(self, request):
        data = body(ReadInput, request)
        return success(svc.mark_read(request.user, data))


class Subscriptions(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SubscriptionInput, responses=responses(SubscriptionResponse, 201)
    )
    def post(self, request):
        data = body(SubscriptionInput, request)
        row, created = svc.record_subscription(request.user, data)
        return success(svc.subscription_data(row), http_status=201 if created else 200)


class TemplateVersion(StrictInput):
    expected_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(min_length=1, max_length=100, trim_whitespace=True)
    body = serializers.CharField(min_length=1, max_length=1000, trim_whitespace=True)
    variables = serializers.ListField(
        child=serializers.CharField(max_length=40), max_length=20
    )


class TemplateActivate(StrictInput):
    version = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=1)


class Preview(serializers.Serializer):
    title = serializers.CharField()
    body = serializers.CharField()


class NotificationTemplateData(serializers.Serializer):
    id = serializers.CharField()
    event_type = serializers.CharField()
    channel = serializers.CharField()
    version = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()
    variables = serializers.ListField(child=serializers.CharField())
    enabled = serializers.BooleanField()
    active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    supported_variables = serializers.ListField(child=serializers.CharField())
    preview = Preview()


class NotificationTemplateResponse(EnvelopeSerializer):
    data = NotificationTemplateData()


class TemplatePage(serializers.Serializer):
    count = serializers.IntegerField()
    page_size = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = NotificationTemplateData(many=True)


class TemplatePageResponse(EnvelopeSerializer):
    data = TemplatePage()


class TemplateList(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        operation_id="operator_notification_template_list",
        responses=responses(TemplatePageResponse),
        parameters=[
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        pager = StandardPagination()
        rows = NotificationTemplate.objects.order_by("event_type", "-version")
        page = pager.paginate_queryset(rows, request)
        return pager.get_paginated_response([svc.template_data(row) for row in page])


class TemplateDetail(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        operation_id="operator_notification_template_retrieve",
        responses=responses(NotificationTemplateResponse),
    )
    def get(self, request, pk):
        return success(
            svc.template_data(get_object_or_404(NotificationTemplate, pk=pk))
        )

    @extend_schema(
        request=TemplateVersion, responses=responses(NotificationTemplateResponse)
    )
    def patch(self, request, pk):
        return success(
            svc.revise_template(request.user, pk, body(TemplateVersion, request))
        )


class TemplateActivateView(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        request=TemplateActivate,
        responses=responses(NotificationTemplateResponse),
        parameters=[HEADER],
    )
    def post(self, request, pk):
        data = body(TemplateActivate, request)
        return success(svc.activate_template(request.user, pk, data, key(request)))
