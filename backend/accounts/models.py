import uuid

from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(
        "手机号",
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="买家注册必填；管理员账号可为空",
    )
    phone_verified_at = models.DateTimeField("手机号验证时间", null=True, blank=True)
    nickname = models.CharField("昵称", max_length=50, blank=True)
    session_version = models.PositiveIntegerField("会话版本", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "accounts_profile"
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"
        permissions = [("manage_roles", "可以管理用户角色")]


class AuthSession(models.Model):
    class ClientKind(models.TextChoices):
        WEB = "web", "Web"
        MINI = "mini", "小程序"

    session_id = models.UUIDField(
        "会话ID", default=uuid.uuid4, unique=True, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_sessions"
    )
    client_kind = models.CharField(
        "客户端类型", max_length=10, choices=ClientKind.choices, default=ClientKind.WEB
    )
    refresh_digest = models.CharField("refresh摘要", max_length=64)
    csrf_digest = models.CharField("CSRF摘要", max_length=64)
    expires_at = models.DateTimeField("过期时间")
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "accounts_session"
        indexes = [models.Index(fields=["user", "revoked_at"])]


class VerificationChallenge(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register", "注册"
        PASSWORD_RESET = "password_reset", "密码找回"
        PHONE_BIND = "phone_bind", "手机绑定"
        REAUTH = "reauth", "再次认证"

    challenge_id = models.UUIDField(
        "挑战ID", default=uuid.uuid4, unique=True, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_challenges",
        null=True,
        blank=True,
    )
    purpose = models.CharField("用途", max_length=32, choices=Purpose.choices)
    target_digest = models.CharField("目标摘要", max_length=64)
    code_digest = models.CharField("验证码摘要", max_length=64)
    attempts = models.PositiveIntegerField("尝试次数", default=0)
    expires_at = models.DateTimeField("过期时间")
    consumed_at = models.DateTimeField("消费时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "accounts_verification"
        indexes = [models.Index(fields=["purpose", "expires_at"])]


class RoleAction(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="role_admin_actions",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="role_change_history",
    )
    action = models.CharField(max_length=16)
    key = models.UUIDField()
    digest = models.CharField(max_length=64)
    reason = models.CharField(max_length=200)
    snapshot = models.JSONField()
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "action", "key"], name="accounts_role_command_once"
            )
        ]
        indexes = [models.Index(fields=["target", "created_at", "id"])]
