import hmac

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from common.constants import ErrorCode
from common.exceptions import BusinessError
from common.response import success

from .models import AuthSession, Profile
from .permissions import CanManageRoles
from .serializers import (
    CsrfResponseSerializer,
    EmptyResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeResponseSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    RoleListResponseSerializer,
    SessionResponseSerializer,
    VerificationSerializer,
)
from .services import (
    authenticate_user,
    consume_challenge,
    create_challenge,
    create_session,
    digest,
    get_valid_session,
    revoke_all_sessions,
    rotate_session,
    user_summary,
)
from .throttles import LoginIdentifierRateThrottle, LoginIPRateThrottle


def require_origin(request):
    origin = request.headers.get("Origin", "").rstrip("/")
    expected = {
        f"{request.scheme}://{request.get_host()}",
        *settings.CORS_ALLOWED_ORIGINS,
    }
    if not origin or origin not in expected:
        raise BusinessError(
            ErrorCode.PERMISSION_DENIED, "请求来源未被允许", http_status=403
        )


def require_csrf(request, session=None):
    require_origin(request)
    header_token = request.headers.get("X-CSRF-Token", "")
    cookie_token = request.COOKIES.get(settings.MALL_CSRF_COOKIE_NAME, "")
    if (
        not header_token
        or not cookie_token
        or not hmac.compare_digest(header_token, cookie_token)
        or (
            session is not None
            and not hmac.compare_digest(session.csrf_digest, digest(header_token))
        )
    ):
        raise BusinessError(
            ErrorCode.PERMISSION_DENIED, "安全校验失败，请刷新后重试", http_status=403
        )


def set_session_cookies(response, refresh, csrf_token):
    for name, value, http_only in (
        (settings.REFRESH_COOKIE_NAME, str(refresh), True),
        (settings.MALL_CSRF_COOKIE_NAME, csrf_token, False),
    ):
        response.set_cookie(
            name,
            value,
            max_age=7 * 24 * 3600,
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=http_only,
            samesite="Lax",
            path="/",
        )
    return response


def session_response(session, refresh, csrf_token, http_status=200):
    from .services import session_payload

    response = success(
        data=session_payload(session, refresh, csrf_token), http_status=http_status
    )
    return set_session_cookies(response, refresh, csrf_token)


def validate_password(password, user=None, field="password"):
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise BusinessError(
            ErrorCode.PASSWORD_TOO_WEAK,
            "密码强度不足",
            errors=[{"field": field, "detail": "; ".join(exc.messages)}],
        ) from exc


class CsrfAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(tags=["身份"], responses={200: CsrfResponseSerializer})
    def get(self, request):
        import secrets

        token = secrets.token_urlsafe(32)
        response = success(data={"csrf_token": token})
        response.set_cookie(
            settings.MALL_CSRF_COOKIE_NAME,
            token,
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=False,
            samesite="Lax",
            path="/",
        )
        return response


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["身份"],
        request=RegisterSerializer,
        responses={
            201: SessionResponseSerializer,
            400: EmptyResponseSerializer,
            409: EmptyResponseSerializer,
        },
    )
    def post(self, request):
        require_csrf(request)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=data["username"]).exists():
            raise BusinessError(ErrorCode.ACCOUNT_EXISTS, "账号已存在", http_status=409)
        if data.get("captcha_id"):
            challenge = consume_challenge(
                data["captcha_id"], "register", data.get("captcha_code", "")
            )
            if not hmac.compare_digest(
                challenge.target_digest, digest(data["username"].lower())
            ):
                raise BusinessError(
                    ErrorCode.CAPTCHA_INVALID, "验证挑战与注册账号不匹配"
                )
        validate_password(data["password"])
        try:
            with transaction.atomic():
                user = user_model.objects.create_user(
                    username=data["username"], password=data["password"]
                )
                Profile.objects.create(user=user, nickname=data["username"])
                user.groups.add(Group.objects.get(name="buyer"))
        except IntegrityError as exc:
            raise BusinessError(
                ErrorCode.ACCOUNT_EXISTS, "账号已存在", http_status=409
            ) from exc
        session, refresh, csrf_token = create_session(user)
        return session_response(session, refresh, csrf_token, http_status=201)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginIdentifierRateThrottle, LoginIPRateThrottle]

    @extend_schema(
        tags=["身份"],
        request=LoginSerializer,
        responses={
            200: SessionResponseSerializer,
            401: EmptyResponseSerializer,
            429: EmptyResponseSerializer,
        },
    )
    def post(self, request):
        require_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_user(**serializer.validated_data)
        if user is None:
            raise BusinessError(
                ErrorCode.LOGIN_FAILED, "账号或密码不正确", http_status=401
            )
        session, refresh, csrf_token = create_session(user)
        return session_response(session, refresh, csrf_token)


class WebRefreshAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(
        tags=["身份"],
        request=None,
        responses={
            200: SessionResponseSerializer,
            401: EmptyResponseSerializer,
            403: EmptyResponseSerializer,
        },
    )
    def post(self, request):
        require_origin(request)
        try:
            token = RefreshToken(request.COOKIES.get(settings.REFRESH_COOKIE_NAME, ""))
            session = get_valid_session(token)
        except Exception as exc:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "登录状态已失效，请重新登录", http_status=401
            ) from exc
        if session is None or session.client_kind != AuthSession.ClientKind.WEB:
            raise BusinessError(
                ErrorCode.TOKEN_INVALID, "登录状态已失效，请重新登录", http_status=401
            )
        require_csrf(request, session)
        session, refresh, csrf_token = rotate_session(
            request.COOKIES[settings.REFRESH_COOKIE_NAME]
        )
        return session_response(session, refresh, csrf_token)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["身份"],
        request=LogoutSerializer,
        responses={200: EmptyResponseSerializer},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = AuthSession.objects.get(session_id=request.auth["session_id"])
        require_csrf(request, session)
        if serializer.validated_data["scope"] == "all":
            revoke_all_sessions(request.user)
        else:
            session.revoked_at = timezone.now()
            session.save(update_fields=["revoked_at", "updated_at"])
        response = success(data=None)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/")
        response.delete_cookie(settings.MALL_CSRF_COOKIE_NAME, path="/")
        return response


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["身份"], responses={200: MeResponseSerializer})
    def get(self, request):
        return success(data=user_summary(request.user))


class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["身份"],
        request=PasswordChangeSerializer,
        responses={200: EmptyResponseSerializer},
    )
    def post(self, request):
        require_origin(request)
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.check_password(data["current_password"]):
            raise BusinessError(
                ErrorCode.INVALID_PARAM,
                "当前密码不正确",
                errors=[{"field": "current_password", "detail": "当前密码不正确"}],
            )
        validate_password(data["new_password"], user=request.user, field="new_password")
        request.user.set_password(data["new_password"])
        request.user.save(update_fields=["password"])
        revoke_all_sessions(request.user)
        return success(data=None)


class VerificationAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["身份"],
        request=VerificationSerializer,
        responses={201: EmptyResponseSerializer, 503: EmptyResponseSerializer},
    )
    def post(self, request):
        require_csrf(request)
        serializer = VerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["purpose"] == "phone_bind":
            if not request.user or not request.user.is_authenticated:
                raise BusinessError(
                    ErrorCode.UNAUTHENTICATED, "请先登录", http_status=401
                )
            user = request.user
        else:
            user = (
                get_user_model().objects.filter(username__iexact=data["target"]).first()
            )
        challenge, code = create_challenge(data["purpose"], data["target"], user=user)
        return success(
            data={
                "challenge_id": str(challenge.challenge_id),
                "expires_at": challenge.expires_at.isoformat(),
                "retry_after_seconds": 60,
                "demo_code": code,
                "delivery": "demo_only_no_sms",
            },
            http_status=201,
        )


class PasswordResetAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["身份"],
        request=PasswordResetSerializer,
        responses={
            200: EmptyResponseSerializer,
            400: EmptyResponseSerializer,
            503: EmptyResponseSerializer,
        },
    )
    def post(self, request):
        require_csrf(request)
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        challenge = consume_challenge(
            data["challenge_id"], "password_reset", data["code"]
        )
        if challenge.user is None:
            raise BusinessError(ErrorCode.CAPTCHA_INVALID, "验证挑战已失效")
        validate_password(
            data["new_password"], user=challenge.user, field="new_password"
        )
        challenge.user.set_password(data["new_password"])
        challenge.user.save(update_fields=["password"])
        revoke_all_sessions(challenge.user)
        return success(data=None)


class RoleListAPIView(APIView):
    permission_classes = [CanManageRoles]

    @extend_schema(
        tags=["权限"],
        responses={200: RoleListResponseSerializer, 403: EmptyResponseSerializer},
    )
    def get(self, request):
        users = get_user_model().objects.prefetch_related("groups").order_by("id")
        return success(
            data=[
                {
                    "id": str(user.id),
                    "username": user.username,
                    "roles": list(user.groups.values_list("name", flat=True)),
                }
                for user in users
            ]
        )
