from uuid import uuid4

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from notifications.models import Notification
from notifications.services import deliver_support_message
from support import services as svc
from support.models import ActiveConversation, SupportCommand, SupportMessage


pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def user_with_group(name, group):
    user = User.objects.create_user(name)
    user.groups.add(Group.objects.get(name=group))
    return user


def post(client, path, data, action_key=None):
    return client.post(
        "/api/v1/" + path,
        data,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(action_key or uuid4()),
    )


def create_buyer_conversation(name="support_buyer"):
    user = User.objects.create_user(name)
    client = client_for(user)
    key = uuid4()
    response = post(client, "conversations/", {}, key)
    assert response.status_code == 201, response.content
    return user, client, response.data["data"], key


def test_permissions_assignment_replay_close_reopen_and_notification():
    buyer, client, conversation, key = create_buyer_conversation()
    conversation_id = conversation["id"]
    replay = post(client, "conversations/", {}, key)
    assert replay.status_code == 200 and replay.data["data"]["id"] == conversation_id
    assert (
        post(client, "conversations/", {"order_no": str(uuid4())}, key).status_code
        == 409
    )
    other = client_for(User.objects.create_user("other_buyer"))
    assert other.get(f"/api/v1/conversations/{conversation_id}/").status_code == 404
    assert (
        post(
            other,
            f"conversations/{conversation_id}/messages/",
            {"client_message_id": str(uuid4()), "body": "越权"},
        ).status_code
        == 404
    )

    agent = user_with_group("agent", "support_agent")
    agent_client = client_for(agent)
    assert (
        agent_client.get(f"/api/v1/ops/conversations/{conversation_id}/").status_code
        == 404
    )
    supervisor = user_with_group("supervisor", "support_supervisor")
    supervisor_client = client_for(supervisor)
    pending = supervisor_client.get("/api/v1/ops/conversations/?scope=pending")
    assert pending.status_code == 200 and pending.data["data"]["count"] == 1
    assigned = post(
        supervisor_client,
        f"ops/conversations/{conversation_id}/assign/",
        {"agent_id": agent.pk, "expected_version": 1, "reason": "分配"},
    )
    assert assigned.status_code == 200, assigned.content
    assert assigned.data["data"]["assigned_agent_id"] == str(agent.pk)
    assert (
        agent_client.get(f"/api/v1/ops/conversations/{conversation_id}/").status_code
        == 200
    )

    message_id = uuid4()
    sent = post(
        agent_client,
        f"ops/conversations/{conversation_id}/messages/",
        {"client_message_id": str(message_id), "body": "你好，已收到咨询"},
    )
    assert sent.status_code == 201
    repeated = post(
        agent_client,
        f"ops/conversations/{conversation_id}/messages/",
        {"client_message_id": str(message_id), "body": "你好，已收到咨询"},
    )
    assert (
        repeated.status_code == 200
        and repeated.data["data"]["id"] == sent.data["data"]["id"]
    )
    conflict = post(
        agent_client,
        f"ops/conversations/{conversation_id}/messages/",
        {"client_message_id": str(message_id), "body": "不同正文"},
    )
    assert conflict.status_code == 409
    message = SupportMessage.objects.get()
    assert deliver_support_message(message.pk)
    assert not deliver_support_message(message.pk)
    notice = Notification.objects.get(event_id=message.notification_event_id)
    assert notice.type == "support" and notice.target_id == conversation_id
    assert "已收到咨询" not in notice.body

    closed = post(
        agent_client,
        f"ops/conversations/{conversation_id}/close/",
        {"reason": "问题已解决"},
    )
    assert closed.status_code == 200 and closed.data["data"]["status"] == "closed"
    assert (
        post(
            client,
            f"conversations/{conversation_id}/messages/",
            {"client_message_id": str(uuid4()), "body": "关闭后发送"},
        ).status_code
        == 409
    )
    assert not ActiveConversation.objects.filter(user=buyer).exists()
    reopened = post(client, "conversations/", {})
    assert (
        reopened.status_code == 201 and reopened.data["data"]["id"] != conversation_id
    )
    assert ActiveConversation.objects.filter(user=buyer).count() == 1
    assert SupportCommand.objects.filter(operation="create").count() == 2


def test_history_cursors_and_read_watermarks_only_move_forward():
    buyer, client, conversation, _ = create_buyer_conversation()
    agent = user_with_group("history_agent", "support_agent")
    supervisor = user_with_group("history_supervisor", "support_supervisor")
    svc.assign_conversation(
        supervisor,
        conversation["id"],
        {"agent_id": agent.pk, "expected_version": 1, "reason": "分配"},
        uuid4(),
    )
    for index in range(1, 6):
        actor = buyer if index % 2 else agent
        svc.send_message(
            actor,
            conversation["id"],
            {"client_message_id": uuid4(), "body": f"消息{index}"},
        )
    path = f"/api/v1/conversations/{conversation['id']}/messages/?limit=2"
    first = client.get(path).data["data"]
    assert [row["conversation_seq"] for row in first["results"]] == ["4", "5"]
    assert first["has_more"]
    second = client.get(path + "&cursor=" + first["next_cursor"]).data["data"]
    assert [row["conversation_seq"] for row in second["results"]] == ["2", "3"]
    third = client.get(path + "&cursor=" + second["next_cursor"]).data["data"]
    assert [row["conversation_seq"] for row in third["results"]] == ["1"]
    assert not third["has_more"]

    newer = client.get(path + "&direction=newer&cursor=" + first["poll_cursor"]).data[
        "data"
    ]
    assert newer["results"] == []
    svc.send_message(
        agent, conversation["id"], {"client_message_id": uuid4(), "body": "消息6"}
    )
    polling = client.get(path + "&direction=newer&cursor=" + first["poll_cursor"]).data[
        "data"
    ]
    assert [row["conversation_seq"] for row in polling["results"]] == ["6"]
    other = client_for(User.objects.create_user("cursor_thief"))
    assert other.get(path + "&cursor=" + first["next_cursor"]).status_code == 404

    messages = {row.conversation_seq: row for row in SupportMessage.objects.all()}
    read = post(
        client,
        f"conversations/{conversation['id']}/read/",
        {"last_message_id": messages[4].pk},
    )
    assert read.data["data"]["last_seq"] == "4"
    assert read.data["data"]["unread_count"] == 1
    backwards = post(
        client,
        f"conversations/{conversation['id']}/read/",
        {"last_message_id": messages[2].pk},
    )
    assert backwards.data["data"]["last_seq"] == "4"
    detail = client.get(f"/api/v1/conversations/{conversation['id']}/").data["data"]
    assert detail["unread_count"] == 1
    agent_client = client_for(agent)
    post(
        agent_client,
        f"ops/conversations/{conversation['id']}/read/",
        {"last_message_id": messages[4].pk},
    )
    detail = client.get(f"/api/v1/conversations/{conversation['id']}/").data["data"]
    assert detail["counterpart_read_seq"] == "4"


def test_order_summary_contains_no_address_and_input_is_strict():
    from datetime import timedelta
    from django.utils import timezone
    from cart.models import Quote
    from orders.models import Order

    buyer = User.objects.create_user("order_support_buyer")
    quote = Quote.objects.create(
        user=buyer, snapshot={}, expires_at=timezone.now() + timedelta(minutes=5)
    )
    order = Order.objects.create(
        user=buyer,
        quote=quote,
        intent_id=uuid4(),
        address_snapshot={"recipient": "不应返回", "phone": "13800000000"},
        goods_amount=1,
        freight_amount=0,
        discount_amount=0,
        payable_amount=1,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    client = client_for(buyer)
    response = post(client, "conversations/", {"order_no": str(order.order_no)})
    assert response.status_code == 201
    summary = response.data["data"]["order_summary"]
    assert summary["order_no"] == str(order.order_no)
    assert "address_snapshot" not in str(response.data) and "不应返回" not in str(
        response.data
    )
    invalid = post(client, "conversations/", {"status": "closed"})
    assert invalid.status_code == 400
    assert APIClient().get("/api/v1/conversations/").status_code == 401
