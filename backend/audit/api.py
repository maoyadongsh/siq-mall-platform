from django.core.paginator import Paginator
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


def entries():
    rows = []
    for row in CatalogEvent.objects.select_related("actor", "product").order_by("-id")[
        :100
    ]:
        rows.append(
            entry(
                row,
                "product",
                row.product_id,
                row.action,
                {"status": row.snapshot.get("status")},
            )
        )
    for row in CategoryEvent.objects.select_related("actor", "category").order_by(
        "-id"
    )[:100]:
        rows.append(
            entry(
                row,
                "category",
                row.category_id,
                row.action,
                {"name": row.snapshot.get("name")},
            )
        )
    for row in Event.objects.select_related("actor", "order").order_by("-id")[:100]:
        rows.append(
            entry(row, "order", row.order.order_no, row.kind, {"reason": row.reason})
        )
    for row in ReviewAction.objects.select_related("actor", "review").order_by("-id")[
        :100
    ]:
        rows.append(
            entry(
                row,
                "review",
                row.review_id,
                row.operation,
                {"to_status": row.to_status, "reason": row.reason},
            )
        )
    for row in ContentAction.objects.select_related("actor", "content").order_by("-id")[
        :100
    ]:
        rows.append(
            entry(
                row,
                "content",
                row.content_id,
                row.operation,
                {"reason": row.reason, "version": row.snapshot.get("version")},
            )
        )
    for row in SupportCommand.objects.select_related("actor", "conversation").order_by(
        "-id"
    )[:100]:
        rows.append(
            entry(row, "support_conversation", row.conversation_id, row.operation, {})
        )
    for row in RoleAction.objects.select_related("actor", "target").order_by("-id")[
        :100
    ]:
        rows.append(
            entry(
                row,
                "user_role",
                row.target_id,
                row.action,
                {"reason": row.reason, **row.snapshot},
            )
        )
    for row in Revision.objects.select_related("actor", "template").order_by("-id")[
        :100
    ]:
        rows.append(
            entry(
                row,
                "coupon_template",
                row.template_id,
                row.action,
                {"version": row.version},
            )
        )
    return sorted(rows, key=lambda row: (row["created_at"], row["id"]), reverse=True)


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
        rows = entries()
        for field in ("object_type", "object_id", "action"):
            if value := request.query_params.get(field):
                rows = [row for row in rows if row[field] == value]
        for field in ("created_after", "created_before"):
            if value := request.query_params.get(field):
                form = serializers.DateTimeField()
                moment = form.to_internal_value(value)
                rows = (
                    [row for row in rows if row["created_at"] >= moment]
                    if field == "created_after"
                    else [row for row in rows if row["created_at"] <= moment]
                )
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
                "results": page.object_list,
            }
        )
