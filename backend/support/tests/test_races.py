from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group, User
from django.db import connection, connections

from support import services as svc
from support.models import ActiveConversation, Conversation, SupportMessage


pytestmark = pytest.mark.django_db(transaction=True)


def race(functions):
    gate = Barrier(len(functions))

    def worker(fn):
        try:
            gate.wait(timeout=30)
            return fn()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(worker, functions))


def require_mysql():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")


def test_one_active_conversation_and_one_message_per_client_id():
    require_mysql()
    buyer = User.objects.create_user("support_race_buyer")
    results = race(
        [lambda: svc.create_conversation(buyer, {}, uuid4()) for _ in range(2)]
    )
    assert len({result[0]["id"] for result in results}) == 1
    assert sorted(result[1] for result in results) == [False, True]
    conversation = Conversation.objects.get(user=buyer)
    assert ActiveConversation.objects.filter(user=buyer).count() == 1
    agent = User.objects.create_user("support_race_agent")
    agent.groups.add(Group.objects.get(name="support_agent"))
    conversation.assigned_agent = agent
    conversation.save(update_fields=["assigned_agent"])
    client_id = uuid4()
    sent = race(
        [
            lambda: svc.send_message(
                agent,
                conversation.pk,
                {"client_message_id": client_id, "body": "同一回复"},
            )
            for _ in range(2)
        ]
    )
    assert len({result[0]["id"] for result in sent}) == 1
    assert sorted(result[1] for result in sent) == [False, True]
    assert SupportMessage.objects.filter(conversation=conversation).count() == 1


def test_assignment_version_conflict_does_not_overwrite_agent():
    require_mysql()
    buyer = User.objects.create_user("assignment_buyer")
    conversation = Conversation.objects.create(user=buyer)
    ActiveConversation.objects.create(user=buyer, conversation=conversation)
    supervisor = User.objects.create_user("assignment_supervisor")
    supervisor.groups.add(Group.objects.get(name="support_supervisor"))
    agents = []
    for index in range(2):
        agent = User.objects.create_user(f"assignment_agent_{index}")
        agent.groups.add(Group.objects.get(name="support_agent"))
        agents.append(agent)

    def assign(agent):
        try:
            return svc.assign_conversation(
                supervisor,
                conversation.pk,
                {"agent_id": agent.pk, "expected_version": 1, "reason": "竞争"},
                uuid4(),
            )
        except Exception as exc:
            from common.exceptions import BusinessError

            if isinstance(exc, BusinessError):
                return exc.code
            raise

    results = race([lambda: assign(agents[0]), lambda: assign(agents[1])])
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count(10008) == 1
    conversation.refresh_from_db()
    assert conversation.version == 2
