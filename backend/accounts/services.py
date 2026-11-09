import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from common.constants import ErrorCode
from common.exceptions import BusinessError

from .models import AuthSession, Profile, VerificationChallenge

REFRESH_LIFETIME = timedelta(days=7)
CHALLENGE_LIFETIME = timedelta(minutes=5)


def digest(value: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def user_summary(user) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        "id": str(user.id),
        "username": user.username,
        "can_fulfill_orders": user.has_perm("orders.fulfill"),
        "can_manage_catalog": user.has_perm("catalog.manage_catalog"),
        "nickname": profile.nickname,
        "has_verified_phone": profile.phone_verified_at is not None,
        "roles": list(user.groups.values_list("name", flat=True)),
    }


def issue_tokens(user, session_id, session_version):
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(lifetime=REFRESH_LIFETIME)
    refresh["session_id"] = str(session_id)
    refresh["session_version"] = session_version
    refresh.access_token["session_id"] = str(session_id)
    refresh.access_token["session_version"] = session_version
    return refresh


def session_payload(session, refresh, csrf_token) -> dict:
    access = refresh.access_token
    return {
        "access": str(access),
        "access_expires_at": timezone.datetime.fromtimestamp(
            access["exp"], tz=UTC
        ).isoformat(),
        "user": user_summary(session.user),
        "session_id": str(session.session_id),
        "csrf_token": csrf_token,
    }


def create_session(user, client_kind=AuthSession.ClientKind.WEB):
    profile, _ = Profile.objects.get_or_create(user=user)
    session_id = uuid.uuid4()
    csrf_token = secrets.token_urlsafe(32)
    refresh = issue_tokens(user, session_id, profile.session_version)
    session = AuthSession.objects.create(
        session_id=session_id,
        user=user,
        client_kind=client_kind,
        refresh_digest=digest(str(refresh)),
        csrf_digest=digest(csrf_token),
        expires_at=timezone.now() + REFRESH_LIFETIME,
    )
    return session, refresh, csrf_token


def get_valid_session(refresh_token):
    if not refresh_token:
        return None
    session = (
        AuthSession.objects.select_related("user", "user__profile")
        .filter(session_id=refresh_token.get("session_id"))
        .first()
    )
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= timezone.now()
        or not hmac.compare_digest(session.refresh_digest, digest(str(refresh_token)))
        or session.user.profile.session_version != refresh_token.get("session_version")
        or not session.user.is_active
    ):
        return None
    return session


def rotate_session(raw_refresh):
    try:
        old_refresh = RefreshToken(raw_refresh)
        session = get_valid_session(old_refresh)
        if session is None:
            raise ValueError("invalid session")
        old_refresh.blacklist()
        refresh = issue_tokens(
            session.user, session.session_id, session.user.profile.session_version
        )
        csrf_token = secrets.token_urlsafe(32)
        session.refresh_digest = digest(str(refresh))
        session.csrf_digest = digest(csrf_token)
        session.expires_at = timezone.now() + REFRESH_LIFETIME
        session.save(
            update_fields=["refresh_digest", "csrf_digest", "expires_at", "updated_at"]
        )
        return session, refresh, csrf_token
    except Exception as exc:
        raise BusinessError(
            ErrorCode.TOKEN_INVALID, "登录状态已失效，请重新登录", http_status=401
        ) from exc


def revoke_all_sessions(user):
    AuthSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    Profile.objects.filter(user=user).update(session_version=F("session_version") + 1)


def authenticate_user(identifier, password):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user = user_model.objects.filter(username__iexact=identifier).first()
    if user is None:
        profile = (
            Profile.objects.select_related("user")
            .filter(phone=identifier, phone_verified_at__isnull=False)
            .first()
        )
        user = profile.user if profile else None
    if user is None:
        return None
    return authenticate(username=user.username, password=password)


def create_challenge(purpose, target, user=None):
    if not settings.DEMO_VERIFICATION_ENABLED:
        raise BusinessError(
            ErrorCode.VERIFICATION_UNAVAILABLE,
            "当前未配置验证渠道，无法完成该操作",
            http_status=503,
        )
    code = f"{secrets.randbelow(1000000):06d}"
    challenge = VerificationChallenge.objects.create(
        challenge_id=uuid.uuid4(),
        user=user,
        purpose=purpose,
        target_digest=digest(target.strip().lower()),
        code_digest=digest(code),
        expires_at=timezone.now() + CHALLENGE_LIFETIME,
    )
    return challenge, code


def consume_challenge(challenge_id, purpose, code):
    with transaction.atomic():
        challenge = (
            VerificationChallenge.objects.select_for_update()
            .filter(
                challenge_id=challenge_id, purpose=purpose, consumed_at__isnull=True
            )
            .first()
        )
        if (
            challenge is None
            or challenge.expires_at <= timezone.now()
            or challenge.attempts >= 5
        ):
            error = BusinessError(ErrorCode.CAPTCHA_INVALID, "验证挑战已失效")
        elif not hmac.compare_digest(challenge.code_digest, digest(code)):
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
            error = BusinessError(ErrorCode.CAPTCHA_INVALID, "验证码不正确或已失效")
        else:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["consumed_at"])
            return challenge
    raise error
