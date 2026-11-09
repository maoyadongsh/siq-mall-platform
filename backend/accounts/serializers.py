from django.conf import settings
from rest_framework import serializers

from common.serializers import EnvelopeSerializer


class RegisterSerializer(serializers.Serializer):
    username = serializers.RegexField(r"^[A-Za-z0-9_]{3,30}$")
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    accepted_terms_version = serializers.CharField()
    captcha_id = serializers.UUIDField(required=False)
    captcha_code = serializers.CharField(required=False, write_only=True)

    def validate_accepted_terms_version(self, value):
        if value != settings.TERMS_VERSION:
            raise serializers.ValidationError("请确认当前版本的服务说明")
        return value


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class UserSummarySerializer(serializers.Serializer):
    can_manage_promotions = serializers.BooleanField()
    can_fulfill_orders = serializers.BooleanField()
    can_manage_catalog = serializers.BooleanField()
    id = serializers.CharField()
    username = serializers.CharField()
    nickname = serializers.CharField(allow_blank=True)
    has_verified_phone = serializers.BooleanField()
    roles = serializers.ListField(child=serializers.CharField())


class SessionDataSerializer(serializers.Serializer):
    access = serializers.CharField()
    access_expires_at = serializers.DateTimeField()
    user = UserSummarySerializer()
    session_id = serializers.UUIDField()
    csrf_token = serializers.CharField()


class SessionResponseSerializer(EnvelopeSerializer):
    data = SessionDataSerializer()


class EmptyResponseSerializer(EnvelopeSerializer):
    data = serializers.JSONField(allow_null=True)


class MeResponseSerializer(EnvelopeSerializer):
    data = UserSummarySerializer()


class CsrfResponseSerializer(EnvelopeSerializer):
    data = serializers.DictField()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class VerificationSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(
        choices=["register", "password_reset", "phone_bind"]
    )
    target = serializers.CharField(max_length=150)


class PasswordResetSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class LogoutSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["current", "all"], default="current")


class RoleUserSerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())


class RoleListResponseSerializer(EnvelopeSerializer):
    data = RoleUserSerializer(many=True)
