import hashlib
import json

from django.contrib.auth.models import Group
from django.db import transaction

from common.constants import ErrorCode
from common.exceptions import BusinessError

from .models import Profile, RoleAction
from .services import revoke_all_sessions


def role_data(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        "id": str(user.pk),
        "username": user.get_username(),
        "roles": [
            {"id": str(group.pk), "name": group.name}
            for group in user.groups.order_by("name")
        ],
        "expected_version": profile.session_version,
    }


def update_roles(actor, target, data, action_key):
    if actor.pk == target.pk:
        raise BusinessError(
            ErrorCode.PERMISSION_DENIED, "不能修改自己的角色", http_status=403
        )
    request_digest = hashlib.sha256(
        json.dumps([target.pk, data], sort_keys=True).encode()
    ).hexdigest()
    with transaction.atomic():
        from django.contrib.auth import get_user_model

        get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
        prior = RoleAction.objects.filter(
            actor=actor, action="update", key=action_key
        ).first()
        if prior:
            if prior.digest != request_digest:
                raise BusinessError(
                    ErrorCode.IDEMPOTENCY_CONFLICT,
                    "提交标识已用于其他角色变更",
                    http_status=409,
                )
            return prior.result
        target = get_user_model().objects.select_for_update().get(pk=target.pk)
        profile, _ = Profile.objects.select_for_update().get_or_create(user=target)
        if profile.session_version != data["expected_version"]:
            raise BusinessError(
                ErrorCode.VERSION_CONFLICT,
                "用户角色或会话版本已变化，请刷新",
                http_status=409,
            )
        groups = list(Group.objects.filter(pk__in=data["role_ids"]))
        if len(groups) != len(set(data["role_ids"])) or len(groups) != len(
            data["role_ids"]
        ):
            raise BusinessError(ErrorCode.INVALID_PARAM, "角色列表包含无效或重复项")
        before = list(target.groups.values_list("name", flat=True))
        target.groups.set(groups)
        revoke_all_sessions(target)
        profile.refresh_from_db()
        target.refresh_from_db()
        result = role_data(target)
        RoleAction.objects.create(
            actor=actor,
            target=target,
            action="update",
            key=action_key,
            digest=request_digest,
            reason=data["reason"],
            snapshot={"before_roles": before, "after_roles": result["roles"]},
            result=result,
        )
        return result
