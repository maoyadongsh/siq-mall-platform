from datetime import UTC

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from cart.api import StrictInput, body
from common.constants import ErrorCode
from common.exceptions import BusinessError
from common.response import success
from common.serializers import EnvelopeSerializer

from .models import AuthSession
from .serializers import LoginSerializer, UserSummarySerializer
from .services import (
    authenticate_user,
    create_session,
    get_valid_session,
    rotate_session,
    user_summary,
)
from .throttles import LoginIdentifierRateThrottle, LoginIPRateThrottle


class MiniRefreshInput(StrictInput):
    refresh = serializers.CharField()


class MiniSessionData(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    access_expires_at = serializers.DateTimeField()
    refresh_expires_at = serializers.DateTimeField()
    session_id = serializers.UUIDField()
    user = UserSummarySerializer()


class MiniSessionResponse(EnvelopeSerializer):
    data = MiniSessionData()


def session_data(session, refresh):
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "access_expires_at": timezone.datetime.fromtimestamp(
            access["exp"], tz=UTC
        ).isoformat(),
        "refresh_expires_at": session.expires_at.isoformat(),
        "session_id": str(session.session_id),
        "user": user_summary(session.user),
    }


class MiniLogin(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginIdentifierRateThrottle, LoginIPRateThrottle]

    @extend_schema(request=LoginSerializer, responses={200: MiniSessionResponse})
    def post(self, request):
        form = LoginSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        user = authenticate_user(**form.validated_data)
        if user is None:
            raise BusinessError(
                ErrorCode.LOGIN_FAILED, "账号或密码不正确", http_status=401
            )
        session, refresh, _ = create_session(user, AuthSession.ClientKind.MINI)
        return success(session_data(session, refresh))


class MiniRefresh(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(request=MiniRefreshInput, responses={200: MiniSessionResponse})
    def post(self, request):
        raw = body(MiniRefreshInput, request)["refresh"]
        try:
            token = RefreshToken(raw)
            session = get_valid_session(token)
        except Exception as exc:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "登录状态已失效，请重新登录", http_status=401
            ) from exc
        if session is None or session.client_kind != AuthSession.ClientKind.MINI:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "登录状态已失效，请重新登录", http_status=401
            )
        session, refresh, _ = rotate_session(raw)
        return success(session_data(session, refresh))


class MiniLogout(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=StrictInput, responses={200: EnvelopeSerializer})
    def post(self, request):
        body(StrictInput, request)
        session = AuthSession.objects.filter(
            session_id=request.auth["session_id"],
            client_kind=AuthSession.ClientKind.MINI,
        ).first()
        if session is None:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "小程序会话不存在", http_status=401
            )
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at", "updated_at"])
        return success(None)
