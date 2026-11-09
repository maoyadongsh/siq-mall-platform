from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from django.core.paginator import Paginator
from django.db.models import F, Value
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from accounts.models import RoleAction
from catalog.models import CatalogEvent, CategoryEvent, Product
from common.exceptions import BusinessError
from common.constants import ErrorCode
from common.response import success
from common.serializers import EnvelopeSerializer
from content.models import Content, ContentAction
from orders.models import Event, Order
from promotions.models import Revision
from reviews.models import Review, ReviewAction
from support.models import Conversation, SupportCommand


class CanViewAudit(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm("audit.view"))


class AuditData(serializers.Serializer):
    id = serializers.CharField()
    object_type = serializers.CharField()
    object_id = serializers.CharField()
    action = serializers.CharField()
    actor = serializers.CharField()
    summary = serializers.DictField()
    created_at = serializers.DateTimeField()


class AuditPage(serializers.Serializer):
    count = serializers.IntegerField()
    page_size = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = AuditData(many=True)


class AuditResponse(EnvelopeSerializer):
    data = AuditPage()


class DashboardResponse(EnvelopeSerializer):
    data = serializers.DictField()


def entry(row, object_type, object_id, action, summary):
    return {
        "id": f"{object_type}:{object_id}:{action}:{row.pk}",
        "object_type": object_type,
        "object_id": str(object_id),
        "action": action,
        "actor": row.actor.get_username() if row.actor else "system",
        "summary": summary,
        "created_at": row.created_at if hasattr(row, "created_at") else row.occurred_at,
    }


@dataclass(frozen=True)
class AuditSource:
    model: type
    object_field: str
    action_field: str
    summary: Callable
    time_field: str = "created_at"


SOURCES = {
    "product": AuditSource(
        CatalogEvent,
        "product_id",
        "action",
        lambda r: {"status": r.snapshot.get("status")},
    ),
    "category": AuditSource(
        CategoryEvent,
        "category_id",
        "action",
        lambda r: {"name": r.snapshot.get("name")},
    ),
    "order": AuditSource(
        Event, "order__order_no", "kind", lambda r: {"reason": r.reason}, "occurred_at"
    ),
    "review": AuditSource(
        ReviewAction,
        "review_id",
        "operation",
        lambda r: {"to_status": r.to_status, "reason": r.reason},
    ),
    "content": AuditSource(
        ContentAction,
        "content_id",
        "operation",
        lambda r: {"reason": r.reason, "version": r.snapshot.get("version")},
    ),
    "support_conversation": AuditSource(
        SupportCommand, "conversation_id", "operation", lambda r: {}
    ),
    "user_role": AuditSource(
        RoleAction, "target_id", "action", lambda r: {"reason": r.reason, **r.snapshot}
    ),
    "coupon_template": AuditSource(
        Revision, "template_id", "action", lambda r: {"version": r.version}
    ),
}


def audit_keys(params):
    bounds = {}
    for param, lookup in (("created_after", "gte"), ("created_before", "lte")):
        if value := params.get(param):
            bounds[lookup] = serializers.DateTimeField().to_internal_value(value)
    queries = []
    for kind, source in SOURCES.items():
        if params.get("object_type") and params["object_type"] != kind:
            continue
        filters = {f"{source.time_field}__{op}": value for op, value in bounds.items()}
        if action := params.get("action"):
            filters[source.action_field] = action
        if raw_id := params.get("object_id"):
            try:
                object_id = UUID(raw_id) if kind == "order" else int(raw_id)
            except ValueError:
                continue
            if str(object_id) != raw_id or (
                kind != "order" and not 0 < object_id < 2**63
            ):
                continue
            filters[source.object_field] = object_id
        keys = (
            source.model.objects.filter(**filters)
            .order_by()
            .annotate(
                audit_time=F(source.time_field),
                source_type=Value(kind),
                event_pk=F("pk"),
            )
            .values_list("audit_time", "source_type", "event_pk")
        )
        queries.append(keys)
    if not queries:
        return []
    combined = (
        queries[0].union(*queries[1:], all=True) if len(queries) > 1 else queries[0]
    )
    return combined.order_by("-audit_time", "source_type", "-event_pk")


def page_entries(keys):
    keys = list(keys)
    rows = {}
    for kind, source in SOURCES.items():
        ids = [pk for _, source_type, pk in keys if kind == source_type]
        if not ids:
            continue
        relations = ("actor", "order") if kind == "order" else ("actor",)
        for row in source.model.objects.filter(pk__in=ids).select_related(*relations):
            object_id = (
                row.order.order_no
                if kind == "order"
                else getattr(row, source.object_field)
            )
            rows[kind, row.pk] = entry(
                row,
                kind,
                object_id,
                getattr(row, source.action_field),
                source.summary(row),
            )
    return [rows[kind, pk] for _, kind, pk in keys]


class Dashboard(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DashboardResponse)
    def get(self, request):
        user = request.user
        tasks = []
        if user.has_perm("orders.fulfill"):
            tasks.append(
                {
                    "key": "pending_shipments",
                    "label": "待发货订单",
                    "count": Order.objects.filter(status="paid").count(),
                    "path": "/ops/orders?status=paid",
                }
            )
        if user.has_perm("reviews.moderate"):
            tasks.append(
                {
                    "key": "pending_reviews",
                    "label": "待审核评价",
                    "count": Review.objects.filter(status="pending").count(),
                    "path": "/ops/reviews?status=pending",
                }
            )
        if user.has_perm("support.reply"):
            tasks.append(
                {
                    "key": "my_support",
                    "label": "我的接待会话",
                    "count": Conversation.objects.filter(
                        assigned_agent=user, status="open"
                    ).count(),
                    "path": "/ops/support",
                }
            )
        if user.has_perm("support.assign"):
            tasks.append(
                {
                    "key": "unassigned_support",
                    "label": "待分配会话",
                    "count": Conversation.objects.filter(
                        assigned_agent__isnull=True, status="open"
                    ).count(),
                    "path": "/ops/support",
                }
            )
        if user.has_perm("catalog.manage_catalog"):
            tasks.append(
                {
                    "key": "draft_products",
                    "label": "商品草稿",
                    "count": Product.objects.filter(status="draft").count(),
                    "path": "/ops/products",
                }
            )
        if user.has_perm("content.publish"):
            tasks.append(
                {
                    "key": "draft_content",
                    "label": "内容草稿",
                    "count": Content.objects.filter(status="draft").count(),
                    "path": "/ops/cms",
                }
            )
        if (
            not tasks
            and not user.has_perm("audit.view")
            and not user.has_perm("accounts.manage_roles")
        ):
            raise BusinessError(
                ErrorCode.PERMISSION_DENIED, "没有运营工作台权限", http_status=403
            )
        return success({"tasks": tasks})


class AuditList(APIView):
    permission_classes = [CanViewAudit]

    @extend_schema(
        responses=AuditResponse,
        parameters=[
            OpenApiParameter("object_type", str),
            OpenApiParameter("object_id", str),
            OpenApiParameter("action", str),
            OpenApiParameter("created_after", str),
            OpenApiParameter("created_before", str),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
    )
    def get(self, request):
        rows = audit_keys(request.query_params)
        try:
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
            page_number = int(request.query_params.get("page", 1))
            if page_size < 1 or page_number < 1:
                raise ValueError
        except ValueError as exc:
            raise serializers.ValidationError("分页参数无效") from exc
        paginator = Paginator(rows, page_size)
        page = paginator.get_page(page_number)
        return success(
            {
                "count": paginator.count,
                "page": page.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "results": page_entries(page.object_list),
            }
        )
