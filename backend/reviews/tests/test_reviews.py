from uuid import uuid4
import pytest
from django.contrib.auth.models import User, Group
from rest_framework.test import APIClient

from orders.tests.test_orders import buyer_fixture, quote, create, post
from orders.models import Order
from reviews.models import Review, ReviewAction

pytestmark = pytest.mark.django_db


def purchase():
    client, user, sku, address = buyer_fixture()
    order = create(client, quote(client, sku, address))
    return (
        client,
        user,
        sku,
        Order.objects.get(order_no=order["order_no"]),
        order["items"][0]["order_item_id"],
    )


def moderator(name="moderator"):
    user = User.objects.create_user(name)
    user.groups.add(Group.objects.get(name="review_moderator"))
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def test_eligibility_limits_and_ownership():
    client, user, sku, order, item = purchase()
    data = {"order_item_id": item, "rating": 1, "content": "  手感偏重  "}
    assert post(APIClient(), "reviews/", data).status_code == 401
    assert post(client, "reviews/", data).data["code"] == 70001
    foreign = APIClient()
    foreign.force_authenticate(User.objects.create_user("foreign", is_staff=True))
    assert post(foreign, "reviews/", data).status_code == 404
    order.status = "completed"
    order.save(update_fields=["status"])
    for bad in (
        {"rating": 0},
        {"rating": 6},
        {"content": "   "},
        {"content": "字" * 501},
        {"status": "approved"},
    ):
        assert post(client, "reviews/", {**data, **bad}).status_code == 400
    assert (
        post(
            client, "reviews/", {**data, "content": "字" * 500, "rating": 5}
        ).status_code
        == 201
    )
    assert post(client, "reviews/", data).data["code"] == 70002
    assert foreign.get("/api/v1/users/me/reviews/").data["data"]["count"] == 0
    assert foreign.get("/api/v1/ops/reviews/").status_code == 403
    assert (
        client.get("/api/v1/users/me/reviews/?order_no=" + str(uuid4())).data["data"][
            "count"
        ]
        == 0
    )


def test_public_projection_moderation_replay_and_hide():
    client, user, sku, order, item = purchase()
    order.status = "completed"
    order.save(update_fields=["status"])
    ops, _ = moderator()
    payload = {"order_item_id": item, "rating": 1, "content": "  尺寸偏小  "}
    key = uuid4()
    first = post(client, "reviews/", payload, key)
    assert first.status_code == 201
    pending = first.data["data"]
    rid = pending["id"]
    product_url = f"/api/v1/products/{sku.product_id}/reviews/"
    path = f"ops/reviews/{rid}/moderate/"
    anon = APIClient()

    def visible():
        return anon.get(product_url).data["data"]

    assert visible()["rating_summary"] == {"count": 0, "average": None}
    assert post(client, "reviews/", {**payload, "rating": 5}, key).data["code"] == 10010
    draft = {"action": "approve", "expected_version": 1}
    assert post(client, path, draft).status_code == 403
    for field in ("content", "rating"):
        assert post(ops, path, {**draft, field: "篡改"}).status_code == 400
    action_key = uuid4()
    allowed = post(ops, path, draft, action_key).data["data"]
    assert post(ops, path, draft, action_key).data["data"] == allowed
    assert allowed["rating"] == 1 and allowed["content"] == "尺寸偏小"
    public = visible()
    assert public["rating_summary"] == {"count": 1, "average": "1.0"}
    assert set(public["results"][0]) == {
        "id",
        "rating",
        "content",
        "created_at",
        "sku_label",
        "author_display",
    }
    assert "address_snapshot" not in allowed
    assert (
        post(
            ops, path, {"action": "hide", "reason": "待复核", "expected_version": 1}
        ).data["code"]
        == 10008
    )
    assert post(ops, path, {"action": "hide", "expected_version": 2}).status_code == 400
    assert (
        post(
            ops,
            path,
            {"action": "hide", "reason": "泄露联系方式", "expected_version": 2},
        ).status_code
        == 200
    )
    assert visible()["results"] == [] and visible()["rating_summary"]["average"] is None
    assert post(ops, path, draft, action_key).data["data"] == allowed
    assert post(client, "reviews/", payload, key).data["data"] == pending
    assert (
        post(ops, path, {"action": "approve", "expected_version": 3}).data["code"]
        == 70003
    )
    own = client.get("/api/v1/users/me/reviews/").data["data"]["results"][0]
    assert own["status"] == "hidden" and own["moderation_reason"] == "泄露联系方式"
    assert ReviewAction.objects.count() == 3
    sku.product.status = "off_sale"
    sku.product.save()
    assert anon.get(product_url).status_code == 404


def test_rejection_and_summary_across_pages():
    client, user, sku, order, item = purchase()
    order.status = "completed"
    order.save(update_fields=["status"])
    ops, _ = moderator()

    def submit(item_id, stars):
        return post(
            client,
            "reviews/",
            {"order_item_id": item_id, "rating": stars, "content": "实际体验"},
        ).data["data"]["id"]

    def decide(rid, action, reason=""):
        return post(
            ops,
            f"ops/reviews/{rid}/moderate/",
            {"action": action, "expected_version": 1, "reason": reason},
        )

    rid = submit(item, 3)
    assert decide(rid, "reject", " ").status_code == 400
    assert decide(rid, "reject", "包含无关广告").status_code == 200
    assert not ops.get("/api/v1/ops/reviews/?status=pending").data["data"]["results"]
    assert (
        client.get("/api/v1/users/me/reviews/").data["data"]["results"][0][
            "moderation_reason"
        ]
        == "包含无关广告"
    )
    for stars in (4, 5):
        o = create(client, quote(client, sku, user.addresses.first()))
        Order.objects.filter(order_no=o["order_no"]).update(status="completed")
        assert (
            decide(submit(o["items"][0]["order_item_id"], stars), "approve").status_code
            == 200
        )
    rows = (
        APIClient()
        .get(f"/api/v1/products/{sku.product_id}/reviews/?page_size=1&page=2")
        .data["data"]
    )
    assert len(rows["results"]) == 1 and rows["rating_summary"] == {
        "count": 2,
        "average": "4.5",
    }
    assert Review.objects.count() == 3
