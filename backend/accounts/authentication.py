from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from accounts.models import AuthSession


class SessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        session_id = validated_token.get("session_id")
        session_version = validated_token.get("session_version")
        if not session_id or session_version is None:
            raise InvalidToken("缺少商城会话信息")
        try:
            session = AuthSession.objects.select_related("user", "user__profile").get(
                session_id=session_id
            )
        except (AuthSession.DoesNotExist, ValueError) as exc:
            raise InvalidToken("商城会话不存在") from exc
        if (
            session.user_id != user.id
            or session.revoked_at is not None
            or session.expires_at <= timezone.now()
            or session.user.profile.session_version != session_version
        ):
            raise InvalidToken("商城会话已失效")
        return user
