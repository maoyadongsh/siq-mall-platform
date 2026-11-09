from uuid import uuid4

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.models import RoleAction
from accounts.services import create_session


pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def grouped(name, group_name):
    user = User.objects.create_user(name)
    user.groups.add(Group.objects.get(name=group_name))
    return user


def test_role_update_replay_version_session_revoke_and_audit():
    admin = grouped("role_admin", "access_admin")
    viewer = grouped("audit_reader", "audit_viewer")
    target = User.objects.create_user("role_target")
    session, _, _ = create_session(target)
    agent_group = Group.objects.get(name="support_agent")
    client = client_for(admin)
    options = client.get("/api/v1/ops/role-options/")
    assert options.status_code == 200
    assert any(row["name"] == "support_agent" for row in options.data["data"])
    assert (
        client.post(
            f"/api/v1/ops/users/{admin.pk}/roles/",
            {"expected_version": 0, "role_ids": [agent_group.pk], "reason": "自助升权"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        ).status_code
        == 403
    )

    key = uuid4()
    data = {"expected_version": 0, "role_ids": [agent_group.pk], "reason": "授权客服"}
    response = client.post(
        f"/api/v1/ops/users/{target.pk}/roles/",
        data,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(key),
    )
    assert response.status_code == 200, response.content
    assert response.data["data"]["expected_version"] == 1
    assert response.data["data"]["roles"][0]["name"] == "support_agent"
    session.refresh_from_db()
    assert session.revoked_at is not None
    replay = client.post(
        f"/api/v1/ops/users/{target.pk}/roles/",
        data,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(key),
    )
    assert replay.data["data"] == response.data["data"]
    assert RoleAction.objects.count() == 1
    stale = client.post(
        f"/api/v1/ops/users/{target.pk}/roles/",
        data,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert stale.status_code == 409
    assert client.get("/api/v1/ops/users/").status_code == 200

    audits = client_for(viewer).get(
        f"/api/v1/ops/audits/?object_type=user_role&object_id={target.pk}"
    )
    assert audits.status_code == 200
    result = audits.data["data"]["results"][0]
    assert result["action"] == "update" and result["actor"] == "role_admin"
    assert result["summary"]["after_roles"][0]["name"] == "support_agent"
    assert "password" not in str(audits.data).lower()
    ordinary = client_for(User.objects.create_user("ordinary_ops", is_staff=True))
    assert ordinary.get("/api/v1/ops/users/").status_code == 403
    assert ordinary.get("/api/v1/ops/audits/").status_code == 403
    assert ordinary.get("/api/v1/ops/dashboard/").status_code == 403
    assert APIClient().get("/api/v1/ops/dashboard/").status_code == 401


def test_dashboard_only_returns_permission_scoped_real_counts():
    user = grouped("dashboard_fulfill", "order_operator")
    client = client_for(user)
    response = client.get("/api/v1/ops/dashboard/")
    assert response.status_code == 200
    tasks = response.data["data"]["tasks"]
    assert [row["key"] for row in tasks] == ["pending_shipments"]
    assert tasks[0]["count"] == 0
    assert "sales" not in str(response.data).lower()
