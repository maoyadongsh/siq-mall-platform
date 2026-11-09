from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.views import APIView

from cart.api import HEADER, StrictInput, body, key
from common.pagination import StandardPagination
from common.response import success
from common.serializers import EnvelopeSerializer, ErrorResponseSerializer

from . import services as svc
from .models import Content


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


class ContentInput(StrictInput):
    kind = serializers.ChoiceField(choices=svc.KINDS)
    slug = serializers.RegexField(
        r"^[a-z0-9][a-z0-9-]{0,79}$", required=False, allow_blank=True
    )
    title = serializers.CharField(max_length=120, trim_whitespace=True)
    blocks = serializers.ListField(
        child=serializers.DictField(), allow_empty=False, max_length=50
    )
    platforms = serializers.ListField(
        child=serializers.ChoiceField(choices=svc.PLATFORMS),
        allow_empty=False,
        default=list(svc.PLATFORMS),
    )
    notify_inbox = serializers.BooleanField(default=False)
    sort_order = serializers.IntegerField(
        min_value=-100000, max_value=100000, default=0
    )
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField(allow_null=True, required=False)


class RevisionInput(StrictInput):
    expected_version = serializers.IntegerField(min_value=1)
    slug = serializers.RegexField(r"^[a-z0-9][a-z0-9-]{0,79}$", required=False)
    title = serializers.CharField(max_length=120, trim_whitespace=True)
    blocks = serializers.ListField(
        child=serializers.DictField(), allow_empty=False, max_length=50
    )
    platforms = serializers.ListField(
        child=serializers.ChoiceField(choices=svc.PLATFORMS), allow_empty=False
    )
    notify_inbox = serializers.BooleanField(default=False)
    sort_order = serializers.IntegerField(min_value=-100000, max_value=100000)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField(allow_null=True, required=False)


class PublishInput(StrictInput):
    revision = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )


class UnpublishInput(PublishInput):
    reason = serializers.CharField(max_length=200, min_length=1, trim_whitespace=True)


class RevisionData(serializers.Serializer):
    revision_no = serializers.IntegerField()
    title = serializers.CharField()
    blocks = serializers.ListField(child=serializers.DictField())
    platforms = serializers.ListField(child=serializers.CharField())
    notify_inbox = serializers.BooleanField()
    sort_order = serializers.IntegerField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class ContentData(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.CharField()
    slug = serializers.CharField()
    status = serializers.CharField()
    publication_state = serializers.CharField()
    version = serializers.IntegerField()
    published_revision = serializers.IntegerField(allow_null=True)
    latest_revision = RevisionData()
    revisions = RevisionData(many=True, required=False)


class ContentResponse(EnvelopeSerializer):
    data = ContentData()


class ContentPage(serializers.Serializer):
    count = serializers.IntegerField()
    page_size = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = ContentData(many=True)


class ContentPageResponse(EnvelopeSerializer):
    data = ContentPage()


class PreviewData(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.CharField()
    slug = serializers.CharField()
    platform = serializers.CharField()
    preview = serializers.BooleanField()
    revision = RevisionData()


class PreviewResponse(EnvelopeSerializer):
    data = PreviewData()


class PublicContentData(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.CharField()
    slug = serializers.CharField()
    revision = RevisionData()


class PublicContentResponse(EnvelopeSerializer):
    data = PublicContentData()


class HomeResponse(EnvelopeSerializer):
    data = serializers.DictField()


class OpsContentList(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        operation_id="operator_cms_list",
        responses=responses(ContentPageResponse),
        parameters=[
            OpenApiParameter("kind", str, enum=list(svc.KINDS)),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        rows = Content.objects.select_related("published_revision").prefetch_related(
            "revisions"
        )
        kind = request.query_params.get("kind")
        if kind:
            if kind not in svc.KINDS:
                raise serializers.ValidationError({"kind": "不支持的内容类型"})
            rows = rows.filter(kind=kind)
        pager = StandardPagination()
        page = pager.paginate_queryset(rows.order_by("-updated_at", "-id"), request)
        return pager.get_paginated_response([svc.content_data(row) for row in page])

    @extend_schema(
        operation_id="operator_cms_create",
        request=ContentInput,
        responses=responses(ContentResponse, 201),
    )
    def post(self, request):
        return success(
            svc.create_content(request.user, body(ContentInput, request)),
            http_status=201,
        )


class OpsContentDetail(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        operation_id="operator_cms_retrieve", responses=responses(ContentResponse)
    )
    def get(self, request, pk):
        row = get_object_or_404(
            Content.objects.select_related("published_revision").prefetch_related(
                "revisions"
            ),
            pk=pk,
        )
        return success(svc.content_data(row, True))


class OpsDraft(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(request=RevisionInput, responses=responses(ContentResponse))
    def patch(self, request, pk):
        return success(
            svc.revise_content(request.user, pk, body(RevisionInput, request))
        )


class OpsPreview(APIView):
    permission_classes = [CanPublishContent]

    @extend_schema(
        responses=responses(PreviewResponse),
        parameters=[
            OpenApiParameter("revision", int, required=True),
            OpenApiParameter("platform", str, enum=list(svc.PLATFORMS)),
        ],
    )
    def get(self, request, pk):
        try:
            revision = int(request.query_params["revision"])
        except (KeyError, ValueError) as exc:
            raise serializers.ValidationError({"revision": "请输入有效版本号"}) from exc
        platform = request.query_params.get("platform", "web")
        if platform not in svc.PLATFORMS:
            raise serializers.ValidationError({"platform": "不支持的展示端"})
        return success(svc.preview(request.user, pk, revision, platform))


class OpsPublication(APIView):
    permission_classes = [CanPublishContent]
    publish = True

    @extend_schema(
        request=PublishInput,
        responses=responses(ContentResponse),
        parameters=[HEADER],
    )
    def post(self, request, pk):
        schema = PublishInput if self.publish else UnpublishInput
        return success(
            svc.change_publication(
                request.user,
                pk,
                body(schema, request),
                key(request),
                self.publish,
            )
        )


class PublicHome(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=responses(HomeResponse),
        parameters=[OpenApiParameter("platform", str, enum=list(svc.PLATFORMS))],
    )
    def get(self, request):
        platform = request.query_params.get("platform", "web")
        if platform not in svc.PLATFORMS:
            raise serializers.ValidationError({"platform": "不支持的展示端"})
        return success(svc.public_home(platform))


class PublicPage(APIView):
    permission_classes = [AllowAny]
    kind = "page"

    @extend_schema(
        responses=responses(PublicContentResponse),
        parameters=[OpenApiParameter("platform", str, enum=list(svc.PLATFORMS))],
    )
    def get(self, request, identifier):
        platform = request.query_params.get("platform", "web")
        if platform not in svc.PLATFORMS:
            raise serializers.ValidationError({"platform": "不支持的展示端"})
        return success(svc.public_detail(self.kind, identifier, platform))


class PublicAnnouncement(PublicPage):
    kind = "announcement"
