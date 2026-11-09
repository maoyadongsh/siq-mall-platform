from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from django.contrib.auth.models import User, Group
from django.utils import timezone
import pytest
from rest_framework.test import APIClient
from orders.tests.test_orders import buyer_fixture, post, create
from catalog.models import Sku, Product
from promotions.models import Template, Coupon
from promotions.services import command, evaluate
from orders.models import Order

pytestmark = pytest.mark.django_db


def rules(**changes):
    now = timezone.now()
    return {
        "name": "满129减20",
        "type": "fixed",
        "threshold_amount": "129.00",
        "reduction_amount": "20.00",
        "scope": "all",
        "product_ids": [],
        "total": 50,
        "per_user_limit": 1,
        "start_at": (now - timedelta(days=1)).isoformat(),
        "end_at": (now + timedelta(days=2)).isoformat(),
        "claim_start_at": (now - timedelta(hours=1)).isoformat(),
        "claim_end_at": (now + timedelta(days=1)).isoformat(),
        **changes,
    }


def publisher():
    u = User.objects.create_user("marketing")
    u.groups.add(Group.objects.get(name="promotion_operator"))
    api = APIClient()
    api.force_authenticate(u)
    return api


def publish(ops, **args):
    draft = ops.post("/api/v1/ops/coupons/", rules(**args), format="json")
    assert draft.status_code == 201, draft.content
    pk = draft.data["data"]["id"]
    r = post(
        ops, f"ops/coupons/{pk}/publish/", {"expected_version": 1, "reason": "演示"}
    )
    assert r.status_code == 200, r.content
    return pk


def claim(api, pk):
    r = post(api, f"coupons/{pk}/claim/", {})
    assert r.status_code == 201, r.content
    return r.data["data"]["id"]


def test_template_validation_limit_separation_and_stop():
    ops = publisher()
    buyer = APIClient()
    buyer.force_authenticate(User.objects.create_user("buyer"))
    assert buyer.post("/api/v1/ops/coupons/", rules(), format="json").status_code == 403
    for change in (
        {"scope": "products"},
        {"type": "percentage"},
        {"discount_bps": 200},
        {"total": 0},
        {"claim_end_at": (timezone.now() + timedelta(weeks=1)).isoformat()},
    ):
        assert (
            ops.post("/api/v1/ops/coupons/", rules(**change), format="json").status_code
            == 400
        )
    pk = publish(ops)
    key = uuid4()
    original = post(buyer, f"coupons/{pk}/claim/", {}, key)
    assert original.status_code == 201
    assert (
        post(buyer, f"coupons/{pk}/claim/", {}, key).data["data"]
        == original.data["data"]
    )
    assert post(buyer, f"coupons/{pk}/claim/", {}).status_code == 409
    assert APIClient().get("/api/v1/coupons/").data["data"]["count"] == 1
    assert (
        ops.patch(
            f"/api/v1/ops/coupons/{pk}/",
            {"expected_version": 2, "total": 999},
            format="json",
        ).status_code
        == 409
    )
    assert (
        post(
            ops,
            f"ops/coupons/{pk}/stop-claiming/",
            {"expected_version": 2, "reason": "活动结束"},
        ).status_code
        == 200
    )
    assert APIClient().get("/api/v1/coupons/").data["data"]["count"] == 0
    assert (
        buyer.get("/api/v1/users/me/coupons/?status=unused").data["data"]["count"] == 1
    )


def test_scoped_percent_quote_and_reserved_payment_after_expiry():
    client, user, sku, address = buyer_fixture()
    ops = publisher()
    other = Product.objects.create(
        category=sku.product.category, title="其他", status="on_sale"
    )
    excluded = Sku.objects.create(
        product=other, label="X", price="90.00", available_stock=2
    )
    pk = publish(
        ops,
        type="percentage",
        discount_bps=2500,
        cap_amount="8.00",
        threshold_amount="99.00",
        reduction_amount=None,
        scope="products",
        product_ids=[sku.product_id],
    )
    coupon = claim(client, pk)

    def preview(lines, c=coupon):
        return client.post(
            "/api/v1/checkout/quote/",
            {"items": lines, "address_id": address.pk, "user_coupon_id": c},
            format="json",
        )

    items = [{"sku_id": sku.pk, "quantity": 1}, {"sku_id": excluded.pk, "quantity": 1}]
    assert preview([items[1]]).status_code == 409
    foreign = User.objects.create_user("foreign")
    other_coupon = command(foreign, int(pk), "claim", uuid4(), {})
    assert preview(items, other_coupon["id"]).status_code == 404
    # Stopping claims does not invalidate either claimed coupon.
    post(
        ops,
        f"ops/coupons/{pk}/stop-claiming/",
        {"expected_version": 2, "reason": "结束"},
    )
    quoted = preview(items).data["data"]
    assert [r["discount_allocated"] for r in quoted["items"]] == ["8.00", "0.00"]
    assert quoted["payable_amount"] == "181.00" and quoted["freight_amount"] == "0.00"
    no = create(client, quoted["quote_id"])["order_no"]
    c = Coupon.objects.get(pk=coupon)
    assert c.status == "reserved"
    assert preview(items).status_code == 409
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    Coupon.objects.filter(pk=c.pk).update(end_at=timezone.now() - timedelta(seconds=1))
    assert (
        post(client, f"payments/{pay}/simulate/", {"outcome": "success"}).status_code
        == 200
    )
    c.refresh_from_db()
    assert c.status == "used" and c.order.order_no == Order.objects.get().order_no
    detail = client.get(f"/api/v1/orders/{no}/").data["data"]
    assert detail["coupon_snapshot"]["cap_amount"] == "8.00"
    assert ops.get("/api/v1/ops/coupons/").data["data"]["results"][0]["used"] == 1


def test_cancel_release_expiry_and_zero_payable():
    client, user, sku, address = buyer_fixture()
    ops = publisher()
    sku.price = "129.00"
    sku.save()
    pk = publish(ops, reduction_amount="200.00")
    coupon = claim(client, pk)

    def order():
        q = client.post(
            "/api/v1/checkout/quote/",
            {
                "items": [{"sku_id": sku.pk, "quantity": 1}],
                "address_id": address.pk,
                "user_coupon_id": coupon,
            },
            format="json",
        ).data["data"]
        assert q["payable_amount"] == "0.00"
        return create(client, q["quote_id"])["order_no"]

    no = order()
    assert Order.objects.get(order_no=no).status == "pending"
    assert post(client, f"orders/{no}/cancel/", {"reason": "other"}).status_code == 200
    assert Coupon.objects.get(pk=coupon).status == "unused"
    no = order()
    Coupon.objects.filter(pk=coupon).update(end_at=timezone.now())
    Order.objects.filter(order_no=no).update(expires_at=timezone.now())
    from django.core.management import call_command

    call_command("process_order_events")
    call_command("process_order_events")
    assert Coupon.objects.get(pk=coupon).status == "expired"
    assert (
        client.get("/api/v1/users/me/coupons/?status=expired").data["data"]["count"]
        == 1
    )


def test_allocation_dates_and_fractional_cent():
    now = timezone.now()
    c = SimpleNamespace(
        terms={
            "threshold_amount": "0.00",
            "type": "fixed",
            "reduction_amount": "20.00",
            "product_ids": [],
            "scope": "all",
        },
        status="unused",
        start_at=now,
        end_at=now + timedelta(seconds=1),
    )

    def calc(amounts, at=now):
        lines = [
            {"sku_id": str(i + 1), "line_amount": v} for i, v in enumerate(amounts)
        ]
        return evaluate(c, lines, {}, at)

    assert calc(["99.00", "69.00"]) == ("", {1: 1179, 2: 821})
    assert calc(["0.00", "69.00"])[1] == {1: 0, 2: 2000}
    assert calc(["99.00"], c.end_at)[0] == "已过期"
    assert calc(["99.00"], now - timedelta(microseconds=1))[0] == "尚未生效"
    c.terms.update(type="percentage", discount_bps=5000, cap_amount="1.00")
    assert calc(["0.01", "0.01", "0.01"])[1] == {1: 1, 2: 1, 3: 0}


def test_edit_audit_and_claim_window_boundaries():
    from unittest.mock import patch
    from promotions.models import Revision
    from common.exceptions import BusinessError

    ops = publisher()
    future = timezone.now() + timedelta(minutes=5)
    r = ops.post(
        "/api/v1/ops/coupons/", rules(claim_start_at=future.isoformat()), format="json"
    )
    pk = r.data["data"]["id"]
    url = f"/api/v1/ops/coupons/{pk}/"
    assert (
        ops.patch(url, {"expected_version": 0, "name": "x"}, format="json").status_code
        == 400
    )
    assert (
        ops.patch(url, {"expected_version": 2, "name": "x"}, format="json").status_code
        == 409
    )
    assert (
        ops.patch(
            url, {"expected_version": 1, "per_user_limit": 2}, format="json"
        ).status_code
        == 200
    )
    key = uuid4()
    payload = {"expected_version": 2, "reason": "启用"}
    for _ in range(2):
        assert post(ops, f"ops/coupons/{pk}/publish/", payload, key).status_code == 200
    assert (
        post(
            ops, f"ops/coupons/{pk}/publish/", {**payload, "reason": "异参"}, key
        ).data["code"]
        == 10010
    )
    assert list(
        Revision.objects.filter(template_id=pk)
        .order_by("version")
        .values_list("action", flat=True)
    ) == ["create", "edit", "publish"]
    buyer = User.objects.create_user("timebuyer")
    t = Template.objects.get(pk=pk)
    for tstamp, allowed in [
        (t.claim_start_at - timedelta(microseconds=1), False),
        (t.claim_start_at, True),
        (t.claim_end_at - timedelta(microseconds=1), True),
        (t.claim_end_at, False),
    ]:
        with patch("promotions.services.timezone.now", return_value=tstamp):
            if allowed:
                assert command(buyer, t.pk, "claim", uuid4(), {})["status"] == "unused"
            else:
                with pytest.raises(BusinessError):
                    command(buyer, t.pk, "claim", uuid4(), {})
    assert Coupon.objects.filter(user=buyer).count() == 2


def test_used_coupon_and_stock_are_atomic_on_payment_failure(monkeypatch):
    from common.exceptions import BusinessError
    from orders.models import Settlement, Payment
    from orders import services

    client, user, sku, address = buyer_fixture()
    pk = publish(publisher(), threshold_amount="99.00")
    c = claim(client, pk)
    q = client.post(
        "/api/v1/checkout/quote/",
        {
            "items": [{"sku_id": sku.pk, "quantity": 1}],
            "address_id": address.pk,
            "user_coupon_id": c,
        },
        format="json",
    ).data["data"]
    assert (q["payable_amount"], q["freight_amount"]) == ("87.00", "8.00")
    no = create(client, q["quote_id"])["order_no"]
    pay = post(client, "payments/", {"order_no": no}).data["data"]["pay_no"]
    key = uuid4()

    def crash(*args):
        raise BusinessError(60002, "故障注入", http_status=409)

    with monkeypatch.context() as m:
        m.setattr(services, "finish_coupon", crash)
        assert (
            post(
                client, f"payments/{pay}/simulate/", {"outcome": "success"}, key
            ).status_code
            == 409
        )
    sku.refresh_from_db()
    assert sku.reserved_stock == 1 and not Settlement.objects.exists()
    assert Coupon.objects.get(pk=c).status == "reserved"
    assert (
        Payment.objects.get().status == "init"
        and Order.objects.get().status == "pending"
    )
    assert (
        post(
            client, f"payments/{pay}/simulate/", {"outcome": "success"}, key
        ).status_code
        == 200
    )
    assert Coupon.objects.get(pk=c).status == "used"


def test_quote_repricing_and_threshold_reconfirmation():
    client, user, sku, address = buyer_fixture()
    ops = publisher()
    pk = publish(ops, total=1)
    coupon = claim(client, pk)
    outsider = APIClient()
    outsider.force_authenticate(User.objects.create_user("outsider"))
    assert post(outsider, f"coupons/{pk}/claim/", {}).status_code == 409
    assert (
        post(
            ops,
            f"ops/coupons/{pk}/stop-claiming/",
            {"expected_version": 1, "reason": "过期版本"},
        ).data["code"]
        == 10008
    )
    assert (
        post(
            ops,
            f"ops/coupons/{pk}/publish/",
            {"expected_version": 2, "reason": "重复发布"},
        ).status_code
        == 409
    )
    req = {"items": [{"sku_id": sku.pk, "quantity": 1}], "address_id": address.pk}
    none = client.post("/api/v1/checkout/quote/", req, format="json").data["data"]
    assert none["selected_coupon"] is None and not none["available_coupons"]
    assert none["unavailable_coupons"][0]["reason"] == "适用商品金额未达门槛"
    req["user_coupon_id"] = coupon
    assert client.post("/api/v1/checkout/quote/", req, format="json").status_code == 409
    sku.price = "129.00"
    sku.save()
    agreed = client.post("/api/v1/checkout/quote/", req, format="json").data["data"]
    sku.price = "130.00"
    sku.save()
    response = post(
        client, "orders/", {"intent_id": str(uuid4()), "quote_id": agreed["quote_id"]}
    )
    assert response.data["code"] == 40005
    assert (
        not Order.objects.exists() and Coupon.objects.get(pk=coupon).status == "unused"
    )
    corrected = client.post("/api/v1/checkout/quote/", req, format="json").data["data"]
    assert corrected["payable_amount"] == "110.00"


def test_subcent_ineligible_and_used_coupon_reason():
    now = timezone.now()
    coupon = SimpleNamespace(
        status="unused",
        start_at=now,
        end_at=now + timedelta(hours=1),
        terms={
            "type": "percentage",
            "threshold_amount": "0.00",
            "discount_bps": 1,
            "cap_amount": "1.00",
            "scope": "all",
            "product_ids": [],
        },
    )
    lines = [{"sku_id": "1", "line_amount": "0.01"}]
    assert evaluate(coupon, lines, {}, now)[0] == "当前优惠不足一分"
    coupon.status = "used"
    assert evaluate(coupon, lines, {}, now)[0] == "已核销"
