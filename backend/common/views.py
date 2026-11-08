"""基础视图：健康检查与旧 JSON refresh 过渡兼容。"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from common import health
from common.constants import ErrorCode
from common.exceptions import BusinessError
from common.response import api_response, now_iso, success
from common.serializers import (
    ErrorResponseSerializer,
    HealthResponseSerializer,
    RefreshResponseSerializer,
)


class HealthCheckView(APIView):
    """GET /api/v1/health/

    返回服务自身状态与数据库/Redis 连通性；任一依赖异常时 HTTP 503 + status=degraded，
    便于 systemd / Nginx / 监控探针直接按状态码判定。
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        summary="健康检查",
        tags=["基础"],
        responses={200: HealthResponseSerializer, 503: HealthResponseSerializer},
    )
    def get(self, request):
        checks = {
            "database": health.check_database().as_dict(),
            "redis": health.check_cache().as_dict(),
        }
        healthy = all(item["status"] == "ok" for item in checks.values())
        data = {
            "service": "mall-api",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "status": "ok" if healthy else "degraded",
            "checks": checks,
            "server_time": now_iso(),
        }
        return api_response(
            data=data,
            message="ok" if healthy else "依赖服务异常",
            http_status=200 if healthy else 503,
        )


class TokenRefreshAPIView(APIView):
    """POST /api/v1/auth/refresh/ —— 刷新 access，refresh 轮换并加入黑名单。"""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        summary="刷新 access token",
        tags=["鉴权"],
        request=TokenRefreshSerializer,
        responses={
            200: RefreshResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            raw_refresh = request.data.get("refresh")
            if raw_refresh and RefreshToken(raw_refresh).get("session_id"):
                raise BusinessError(
                    ErrorCode.TOKEN_INVALID,
                    "请使用当前客户端的刷新接口",
                    http_status=401,
                )
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken) as exc:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "refresh 已失效，请重新登录", http_status=401
            ) from exc
        return success(data=serializer.validated_data)
