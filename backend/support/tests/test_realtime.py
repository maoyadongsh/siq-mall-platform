from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group, User
from django.test import override_settings
from rest_framework.test import APIClient

from config.asgi import application
from support import realtime
from support import services as svc

pytestmark = pytest.mark.django_db(transaction=True)


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


def create_conversation(name="ws_buyer"):
    buyer = User.objects.create_user(name)
    client = client_for(buyer)
    response = post(client, "conversations/", {})
    assert response.status_code == 201, response.content
    return buyer, client, response.data["data"]


def issue(client, conversation_id, ops=False):
    path = "ops/conversations/ws-ticket/" if ops else "conversations/ws-ticket/"
    return post(client, path, {"conversation_id": conversation_id})


def test_ticket_is_owner_scoped_one_time_and_disabled_by_switch():
    buyer, client, conversation = create_conversation()
    conversation_id = int(conversation["id"])
    response = issue(client, conversation_id)
    assert response.status_code == 200, response.content
    data = response.data["data"]
    assert data["path"] == f"/ws/support/{conversation_id}/"
    payload = realtime.consume_ticket(data["ticket"], conversation_id)
    assert payload["user_id"] == buyer.pk and payload["ops"] is False
    assert realtime.consume_ticket(data["ticket"], conversation_id) is None

    other = client_for(User.objects.create_user("ws_other"))
    assert issue(other, conversation_id).status_code == 404

    with override_settings(SUPPORT_WS_ENABLED=False):
        assert issue(client, conversation_id).status_code == 503


def test_ops_ticket_requires_assignment_then_allows_agent():
    buyer, buyer_client, conversation = create_conversation("ws_buyer_ops")
    conversation_id = int(conversation["id"])
    agent = user_with_group("ws_agent", "support_agent")
    agent_client = client_for(agent)
    assert issue(agent_client, conversation_id, ops=True).status_code == 404

    supervisor = user_with_group("ws_supervisor", "support_supervisor")
    supervisor_client = client_for(supervisor)
    assigned = post(
        supervisor_client,
        f"ops/conversations/{conversation_id}/assign/",
        {"agent_id": agent.pk, "expected_version": 1, "reason": "分配"},
    )
    assert assigned.status_code == 200, assigned.content
    response = issue(agent_client, conversation_id, ops=True)
    assert response.status_code == 200, response.content
    payload = realtime.consume_ticket(response.data["data"]["ticket"], conversation_id)
    assert payload["user_id"] == agent.pk and payload["ops"] is True
    assert issue(buyer_client, conversation_id, ops=True).status_code == 403


def test_consumer_rejects_invalid_ticket_and_accepts_issued_ticket():
    _, client, conversation = create_conversation("ws_buyer_connect")
    conversation_id = int(conversation["id"])

    invalid = WebsocketCommunicator(
        application,
        f"/ws/support/{conversation_id}/",
        subprotocols=["support.ticket.invalid"],
    )
    connected, code = async_to_sync(invalid.connect)()
    assert connected is False and code == 4401

    ticket = issue(client, conversation_id).data["data"]["ticket"]

    async def session():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/support/{conversation_id}/",
            subprotocols=[f"support.ticket.{ticket}"],
        )
        connected, _ = await communicator.connect()
        assert connected is True
        ready = await communicator.receive_json_from()
        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from()
        await communicator.disconnect()
        return ready, pong

    ready, pong = async_to_sync(session)()
    assert ready["type"] == "ready" and ready["conversation_id"] == str(conversation_id)
    assert pong["type"] == "pong"


def test_message_and_close_commit_broadcast_payloads(monkeypatch):
    buyer, _, conversation = create_conversation("ws_buyer_broadcast")
    conversation_id = int(conversation["id"])
    events = []
    monkeypatch.setattr(
        realtime,
        "broadcast_message",
        lambda cid, message, sender_id=None: events.append((cid, message)),
    )
    monkeypatch.setattr(
        realtime, "broadcast_closed", lambda cid: events.append((cid, "closed"))
    )

    message, created = svc.send_message(
        buyer,
        conversation_id,
        {"client_message_id": str(uuid4()), "body": "实时消息"},
    )
    assert created is True
    assert events[0][0] == conversation_id
    assert events[0][1]["body"] == message["body"]

    svc.close_conversation(buyer, conversation_id, {"reason": "结束咨询"}, uuid4())
    assert events[-1] == (conversation_id, "closed")
