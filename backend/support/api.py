from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from cart.api import HEADER, StrictInput, body, key
from common.constants import ErrorCode as Code
from common.exceptions import BusinessError
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer

from . import services as svc
from .models import Conversation


def responses(schema, status=200):
    return {
        status: schema,
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }


class CanReply(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("support.reply"))


class CanAssign(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("support.assign"))


class CanSupportWork(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and (
                request.user.has_perm("support.reply")
                or request.user.has_perm("support.assign")
            )
        )


class CreateInput(StrictInput):
    order_no = serializers.UUIDField(required=False)


class MessageInput(StrictInput):
    client_message_id = serializers.UUIDField()
    body = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)


class SupportReadInput(StrictInput):
    last_message_id = serializers.IntegerField(min_value=1)


class CloseInput(StrictInput):
    reason = serializers.CharField(
        max_length=100, default="结束咨询", trim_whitespace=True
    )


class AssignInput(StrictInput):
    agent_id = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=200, allow_blank=True, default="")


class MessageData(serializers.Serializer):
    id = serializers.CharField()
    conversation_id = serializers.CharField()
    conversation_seq = serializers.CharField()
    sender_role = serializers.CharField()
    client_message_id = serializers.UUIDField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()


class SupportOrderSummary(serializers.Serializer):
    order_no = serializers.UUIDField()
    status = serializers.CharField()
    payable_amount = serializers.CharField()
    currency = serializers.CharField()
    items = serializers.ListField(child=serializers.DictField())


class ConversationData(serializers.Serializer):
    id = serializers.CharField()
    buyer_display_name = serializers.CharField()
    status = serializers.CharField()
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    close_reason = serializers.CharField()
    assigned_agent_id = serializers.CharField(allow_null=True)
    assigned_agent_display_name = serializers.CharField(allow_null=True)
    last_message = MessageData(allow_null=True)
    unread_count = serializers.IntegerField()
    counterpart_read_seq = serializers.CharField()
    order_summary = SupportOrderSummary(allow_null=True)
    can_reply = serializers.BooleanField()
    can_close = serializers.BooleanField()


class ConversationResponse(EnvelopeSerializer):
    data = ConversationData()


class ConversationPage(serializers.Serializer):
    count = serializers.IntegerField()
    page_size = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = ConversationData(many=True)


class ConversationPageResponse(EnvelopeSerializer):
    data = ConversationPage()


class MessageResponse(EnvelopeSerializer):
    data = MessageData()


class HistoryData(serializers.Serializer):
    results = MessageData(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()
    poll_cursor = serializers.CharField(allow_null=True)


class SupportHistoryResponse(EnvelopeSerializer):
    data = HistoryData()


class ReadData(serializers.Serializer):
    last_seq = serializers.CharField()
    last_message_id = serializers.CharField(allow_null=True)
    unread_count = serializers.IntegerField()


class SupportReadResponse(EnvelopeSerializer):
    data = ReadData()


class ConversationList(APIView):
    permission_classes = [IsAuthenticated]
    ops = False

    @extend_schema(
        operation_id="buyer_conversation_list",
        responses=responses(ConversationPageResponse),
        parameters=[OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
    )
    def get(self, request):
        rows = Conversation.objects.filter(user=request.user)
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-updated_at", "-id"), request)
        return pager.get_paginated_response(
            [svc.conversation_data(row, request.user) for row in page]
        )

    @extend_schema(
        request=CreateInput,
        responses=responses(ConversationResponse, 201),
        parameters=[HEADER],
    )
    def post(self, request):
        data, created = svc.create_conversation(
            request.user, body(CreateInput, request), key(request)
        )
        return success(data, http_status=201 if created else 200)


class OpsConversationList(ConversationList):
    permission_classes = [CanSupportWork]
    ops = True

    @extend_schema(
        operation_id="operator_conversation_list",
        responses=responses(ConversationPageResponse),
        parameters=[
            OpenApiParameter("scope", str, enum=["mine", "pending", "closed", "all"]),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        scope = request.query_params.get("scope", "mine")
        if scope not in {"mine", "pending", "closed", "all"}:
            raise serializers.ValidationError({"scope": "不支持的队列范围"})
        if scope != "mine" and not request.user.has_perm("support.assign"):
            raise BusinessError(
                Code.PERMISSION_DENIED, "没有查看该客服队列的权限", http_status=403
            )
        rows = Conversation.objects.all()
        if scope == "mine":
            rows = rows.filter(assigned_agent=request.user, status="open")
        elif scope == "pending":
            rows = rows.filter(assigned_agent__isnull=True, status="open")
        elif scope == "closed":
            rows = rows.filter(status="closed")
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-updated_at", "-id"), request)
        return pager.get_paginated_response(
            [svc.conversation_data(row, request.user) for row in page]
        )


class ConversationDetail(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="buyer_conversation_retrieve",
        responses=responses(ConversationResponse),
    )
    def get(self, request, pk):
        row = get_object_or_404(Conversation, pk=pk)
        svc.authorize(row, request.user)
        return success(svc.conversation_data(row, request.user))


class OpsConversationDetail(ConversationDetail):
    permission_classes = [CanReply]

    @extend_schema(
        operation_id="operator_conversation_retrieve",
        responses=responses(ConversationResponse),
    )
    def get(self, request, pk):
        return super().get(request, pk)


class Messages(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=responses(SupportHistoryResponse),
        parameters=[
            OpenApiParameter("cursor", str),
            OpenApiParameter("limit", int),
            OpenApiParameter("direction", str, enum=["older", "newer"]),
        ],
    )
    def get(self, request, pk):
        direction = request.query_params.get("direction", "older")
        if direction not in {"older", "newer"}:
            raise serializers.ValidationError({"direction": "仅支持older或newer"})
        try:
            limit = min(int(request.query_params.get("limit", 20)), 100)
            if limit < 1:
                raise ValueError
        except ValueError as exc:
            raise serializers.ValidationError({"limit": "请输入1–100的整数"}) from exc
        return success(
            svc.history(
                request.user,
                pk,
                request.query_params.get("cursor"),
                limit,
                direction,
            )
        )

    @extend_schema(
        request=MessageInput,
        responses=responses(MessageResponse, 201),
        parameters=[HEADER],
    )
    def post(self, request, pk):
        data = body(MessageInput, request)
        key(request)
        result, created = svc.send_message(request.user, pk, data)
        return success(result, http_status=201 if created else 200)


class OpsMessages(Messages):
    permission_classes = [CanReply]


class Read(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SupportReadInput, responses=responses(SupportReadResponse))
    def post(self, request, pk):
        return success(
            svc.mark_read(
                request.user, pk, body(SupportReadInput, request)["last_message_id"]
            )
        )


class OpsRead(Read):
    permission_classes = [CanReply]


class Close(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CloseInput,
        responses=responses(ConversationResponse),
        parameters=[HEADER],
    )
    def post(self, request, pk):
        return success(
            svc.close_conversation(
                request.user, pk, body(CloseInput, request), key(request)
            )
        )


class OpsClose(Close):
    permission_classes = [CanReply]


class Assign(APIView):
    permission_classes = [CanAssign]

    @extend_schema(
        request=AssignInput,
        responses=responses(ConversationResponse),
        parameters=[HEADER],
    )
    def post(self, request, pk):
        return success(
            svc.assign_conversation(
                request.user, pk, body(AssignInput, request), key(request)
            )
        )
