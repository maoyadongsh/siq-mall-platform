from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient

from cart.models import Quote
from notifications import services as svc
from notifications.models import (
    Notification,
    NotificationConsumption,
    NotificationSubscription,
    NotificationTemplate,
    NotificationTemplateAction,
)
from notifications.services import TemplateConfigurationError
from orders.models import Event, Order, OrderActivity
from orders.tests.test_orders import buyer_fixture, create, post, quote


pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_event(user, kind="order.paid"):
    quote_row = Quote.objects.create(
        user=user, snapshot={}, expires_at=timezone.now() + timedelta(minutes=5)
    )
    order = Order.objects.create(
        user=user,
        quote=quote_row,
        intent_id=uuid4(),
        address_snapshot={"detail": "不应进入通知"},
        goods_amount=0,
        freight_amount=0,
        discount_amount=0,
        payable_amount=0,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    return Event.objects.create(order=order, kind=kind, actor=user)


def pay_ship_receive(client, user, sku, address):
    order = create(client, quote(client, sku, address))
    no = order["order_no"]
    payment = post(client, "payments/", {"order_no": no}).data["data"]
    assert (
        post(
            client,
            f"payments/{payment['pay_no']}/simulate/",
            {"outcome": "success"},
        ).status_code
        == 200
    )
    operator = User.objects.create_user("notification_shipper")
    operator.groups.add(Group.objects.get(name="order_operator"))
    ops = client_for(operator)
    assert (
        post(
            ops,
            f"ops/orders/{no}/ship/",
            {
                "carrier": "演示物流",
                "tracking_no": "DEMO001",
                "expected_version": 2,
            },
        ).status_code
        == 200
    )
    assert post(client, f"orders/{no}/receive/", {}).status_code == 200
    return no


def test_legal_order_path_generates_one_notice_per_event():
    client, user, sku, address = buyer_fixture()
    no = pay_ship_receive(client, user, sku, address)
    call_command("process_order_events")
    call_command("process_order_events")

    rows = Notification.objects.filter(user=user)
    assert rows.count() == 4
    assert {row.title for row in rows} == {
        "订单已创建",
        "演示支付成功",
        "订单已发货",
        "订单已完成",
    }
    assert {row.target_id for row in rows} == {no}
    assert all(row.type == "order" for row in rows)
    assert all("不应进入" not in row.body for row in rows)
    assert NotificationConsumption.objects.count() == 4
    event_ids = Event.objects.values_list("event_id", flat=True)
    assert not any(
        svc.deliver_order_event(pk) for pk in Event.objects.values_list("pk", flat=True)
    )
    assert set(
        NotificationConsumption.objects.values_list("event_id", flat=True)
    ) == set(event_ids)

    other = client_for(User.objects.create_user("other_buyer"))
    assert other.get("/api/v1/notifications/").data["data"]["results"] == []
    notice_id = str(rows.first().pk)
    response = other.post(
        "/api/v1/notifications/read/", {"ids": [notice_id]}, format="json"
    )
    assert response.data["data"]["updated_count"] == 0
    rows.first().refresh_from_db()
    assert rows.first().read_at is None


def test_cancel_uses_pending_path_and_consumer_failure_can_retry():
    client, user, sku, address = buyer_fixture()
    created = create(client, quote(client, sku, address))
    no = created["order_no"]
    event = Event.objects.get(order__order_no=no, kind="order.created")
    from orders.services import deliver_one

    assert deliver_one(event.pk)
    with patch(
        "notifications.services.create_notice", side_effect=RuntimeError("injected")
    ):
        with pytest.raises(RuntimeError):
            svc.deliver_order_event(event.pk)
    event.refresh_from_db()
    assert event.delivered_at is not None
    assert OrderActivity.objects.filter(event=event).exists()
    assert not NotificationConsumption.objects.filter(event_id=event.event_id).exists()
    assert not Notification.objects.filter(event_id=event.event_id).exists()

    assert svc.deliver_order_event(event.pk)
    assert not svc.deliver_order_event(event.pk)
    assert (
        post(client, f"orders/{no}/cancel/", {"reason": "other"}).data["data"]["status"]
        == "canceled"
    )
    call_command("process_order_events")
    assert set(
        Notification.objects.filter(user=user).values_list("title", flat=True)
    ) == {"订单已创建", "订单已取消"}

    broken = Event.objects.get(order__order_no=no, kind="order.canceled")
    NotificationConsumption.objects.filter(event_id=broken.event_id).delete()
    with patch(
        "notifications.services.create_notice", side_effect=RuntimeError("injected")
    ):
        with pytest.raises(CommandError):
            call_command("process_order_events")
    assert Notification.objects.filter(event_id=broken.event_id).count() == 1
    call_command("process_order_events")
    assert NotificationConsumption.objects.filter(event_id=broken.event_id).exists()


def test_cursor_and_read_watermark_leave_concurrent_new_notice_unread():
    user = User.objects.create_user("reader")
    client = client_for(user)
    first = svc.create_notice(
        user, uuid4(), "order.paid", "order", "order", str(uuid4()), {"order_no": "A"}
    )
    second = svc.create_notice(
        user,
        uuid4(),
        "order.shipped",
        "order",
        "order",
        str(uuid4()),
        {"order_no": "B"},
    )
    page = client.get("/api/v1/notifications/?limit=1").data["data"]
    assert [row["id"] for row in page["results"]] == [str(second.pk)]
    older = client.get(
        "/api/v1/notifications/?limit=1&cursor=" + page["next_cursor"]
    ).data["data"]
    assert [row["id"] for row in older["results"]] == [str(first.pk)]
    assert older["has_more"] is False

    third = svc.create_notice(
        user,
        uuid4(),
        "order.completed",
        "order",
        "order",
        str(uuid4()),
        {"order_no": "C"},
    )
    response = client.post(
        "/api/v1/notifications/read/",
        {"watermark": page["read_watermark"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["data"]["updated_count"] == 2
    assert response.data["data"]["total"] == 1
    third.refresh_from_db()
    assert third.read_at is None
    repeated = client.post(
        "/api/v1/notifications/read/",
        {"watermark": page["read_watermark"]},
        format="json",
    )
    assert repeated.data["data"]["updated_count"] == 0
    assert repeated.data["data"]["total"] == 1
    read_one = client.post(
        "/api/v1/notifications/read/", {"ids": [str(third.pk)]}, format="json"
    )
    assert read_one.data["data"]["total"] == 0
    assert (
        client.post(
            "/api/v1/notifications/read/", {"ids": [str(third.pk)]}, format="json"
        ).data["data"]["total"]
        == 0
    )
    other = client_for(User.objects.create_user("watermark_thief"))
    stolen = other.post(
        "/api/v1/notifications/read/",
        {"watermark": page["read_watermark"]},
        format="json",
    )
    assert stolen.status_code == 400


def test_template_permissions_versions_activation_replay_and_missing_variables():
    ordinary = User.objects.create_user("ordinary", is_staff=True)
    assert (
        client_for(ordinary).get("/api/v1/ops/notification-templates/").status_code
        == 403
    )
    actor = User.objects.create_user("content_editor")
    actor.groups.add(Group.objects.get(name="content_operator"))
    client = client_for(actor)
    rows = client.get("/api/v1/ops/notification-templates/?page_size=100").data["data"][
        "results"
    ]
    current = next(row for row in rows if row["event_type"] == "order.paid")
    response = client.patch(
        f"/api/v1/ops/notification-templates/{current['id']}/",
        {
            "expected_version": current["version"],
            "title": "新的支付提醒 {order_no}",
            "body": "订单 {order_no} 已模拟支付。",
            "variables": ["order_no"],
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    revised = response.data["data"]
    assert revised["version"] == 2 and not revised["active"]
    assert revised["preview"]["title"] == "新的支付提醒 DEMO-PREVIEW"
    invalid = client.patch(
        f"/api/v1/ops/notification-templates/{revised['id']}/",
        {
            "expected_version": 2,
            "title": "越权变量",
            "body": "{address}",
            "variables": ["address"],
        },
        format="json",
    )
    assert invalid.status_code == 400 and invalid.data["code"] == 80002

    user = User.objects.create_user("template_buyer")
    before = make_event(user)
    svc.deliver_order_event(before.pk)
    assert Notification.objects.get(event_id=before.event_id).title == "演示支付成功"
    payload = {"version": 2, "expected_version": 1}
    action_key = uuid4()
    activated = post(
        client,
        f"ops/notification-templates/{revised['id']}/activate/",
        payload,
        action_key,
    )
    assert activated.status_code == 200, activated.content
    assert activated.data["data"]["active"]
    replayed = post(
        client,
        f"ops/notification-templates/{revised['id']}/activate/",
        payload,
        action_key,
    )
    assert replayed.data["data"] == activated.data["data"]
    assert NotificationTemplateAction.objects.count() == 1
    conflict = post(
        client,
        f"ops/notification-templates/{current['id']}/activate/",
        payload,
        action_key,
    )
    assert conflict.status_code == 409
    after = make_event(user)
    svc.deliver_order_event(after.pk)
    assert Notification.objects.get(event_id=after.event_id).title.startswith(
        "新的支付提醒"
    )

    template = NotificationTemplate(
        event_type="order.paid", title="{order_no}", body="正文", variables=["order_no"]
    )
    with pytest.raises(TemplateConfigurationError, match="变量不完整"):
        svc.render(template, {})


def test_review_moderation_is_an_independent_notification_source():
    client, user, sku, address = buyer_fixture()
    no = pay_ship_receive(client, user, sku, address)
    order = client.get(f"/api/v1/orders/{no}/").data["data"]
    review = post(
        client,
        "reviews/",
        {
            "order_item_id": order["items"][0]["order_item_id"],
            "rating": 5,
            "content": "与描述一致",
        },
    ).data["data"]
    moderator = User.objects.create_user("notice_moderator")
    moderator.groups.add(Group.objects.get(name="review_moderator"))
    moderated = post(
        client_for(moderator),
        f"ops/reviews/{review['id']}/moderate/",
        {"action": "approve", "reason": "", "expected_version": 1},
    )
    assert moderated.status_code == 200
    from reviews.models import ReviewAction

    action = ReviewAction.objects.get(review_id=review["id"], operation="moderate")
    assert action.event_id is not None
    assert svc.deliver_review_action(action.pk)
    assert not svc.deliver_review_action(action.pk)
    notice = Notification.objects.get(event_id=action.event_id)
    assert notice.type == "system" and notice.target_type == "review"
    assert "已公开" in notice.body


def test_subscription_result_is_not_delivery_proof_and_replays_safely():
    user = User.objects.create_user("mini_user")
    client = client_for(user)
    payload = {
        "provider": "wechat_mini",
        "template_key": "order-paid-demo",
        "result": "accept",
        "client_event_id": str(uuid4()),
    }
    response = client.post(
        "/api/v1/notifications/subscriptions/", payload, format="json"
    )
    assert response.status_code == 201
    assert response.data["data"]["delivery_status"] == "not_sent"
    replay = client.post("/api/v1/notifications/subscriptions/", payload, format="json")
    assert replay.status_code == 200
    assert replay.data["data"]["id"] == response.data["data"]["id"]
    conflict = client.post(
        "/api/v1/notifications/subscriptions/",
        {**payload, "result": "reject"},
        format="json",
    )
    assert conflict.status_code == 409
    assert NotificationSubscription.objects.count() == 1
