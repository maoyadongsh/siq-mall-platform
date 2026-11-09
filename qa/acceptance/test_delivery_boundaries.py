import json
import subprocess
from pathlib import Path
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from content.tests.test_content import (
    operator,
    payload,
    create,
    publish,
    client_for,
    revision_payload,
)
from notifications import services as ns
from notifications.models import Notification
from users.tests.conftest import address_payload
from users.models import Address

pytestmark = pytest.mark.django_db


@pytest.mark.django_db(transaction=True)
def test_scheduled_announcement():
    buyer = User.objects.create_user("accept_buyer")
    _, ops = operator()
    now = timezone.now()
    c = create(
        ops,
        payload(
            kind="announcement",
            title="EMBARGO_FUTURE",
            notify_inbox=True,
            start_at=(now + timedelta(days=1)).isoformat(),
            end_at=(now + timedelta(days=2)).isoformat(),
        ),
    )
    c = publish(ops, c)
    call_command("process_order_events")
    inbox = Notification.objects.filter(
        user=buyer, body__contains="EMBARGO_FUTURE"
    ).count()
    status = client_for(buyer).get(f"/api/v1/cms/announcements/{c['id']}/").status_code
    print("future announcement: public_http=", status, "premature_notices=", inbox)
    assert status == 404 and inbox == 0
    with patch.object(timezone, "now", return_value=now + timedelta(days=1)):
        call_command("process_order_events")
        call_command("process_order_events")
    assert (
        Notification.objects.filter(user=buyer, body__contains="EMBARGO_FUTURE").count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_withdrawn_replaced_and_expired_revisions_stay_silent():
    buyer = User.objects.create_user("withdrawn_buyer")
    _, ops = operator()
    c = publish(
        ops,
        create(ops, payload(kind="announcement", title="withdrawn", notify_inbox=True)),
    )
    publish(ops, c, action="unpublish")
    c = publish(
        ops,
        create(
            ops, payload(kind="announcement", title="superseded", notify_inbox=True)
        ),
    )
    revised = ops.patch(
        f"/api/v1/ops/cms/{c['id']}/draft/",
        revision_payload(c, title="current", notify_inbox=True),
        format="json",
    )
    publish(ops, revised.data["data"], revision=2)
    now = timezone.now()
    publish(
        ops,
        create(
            ops,
            payload(
                kind="announcement",
                title="expired",
                notify_inbox=True,
                end_at=(now + timedelta(minutes=1)).isoformat(),
            ),
        ),
    )
    with patch.object(timezone, "now", return_value=now + timedelta(minutes=1)):
        call_command("process_order_events")
    notices = Notification.objects.filter(user=buyer)
    assert notices.count() == 1 and "current" in notices.get().body


def test_read_snapshot():
    u = User.objects.create_user("notice_buyer")

    def send():
        return ns.create_notice(
            u, uuid4(), "order.paid", "order", "order", uuid4(), {"order_no": "example"}
        )

    send()
    base = ns.watermark

    def interleave(*args):
        send()
        return base(*args)

    with patch.object(ns, "watermark", side_effect=interleave):
        visible = ns.page(u, None, None, 20)
    res = ns.mark_read(u, {"watermark": visible["read_watermark"]})
    print(
        "rows_visible=",
        len(visible["results"]),
        "marked_read=",
        res["updated_count"],
        "remaining_unread=",
        res["total"],
    )
    assert (
        len(visible["results"]) == 1 and res["updated_count"] == 1 and res["total"] == 1
    )


def test_history_pages_keep_the_first_filtered_watermark():
    u = User.objects.create_user("paged_buyer")

    def send_order():
        return ns.create_notice(
            u, uuid4(), "order.paid", "order", "order", uuid4(), {"order_no": "example"}
        )

    for _ in range(3):
        send_order()
    first = ns.page(u, "order", None, 1)
    new = send_order()
    system = ns.create_notice(
        u,
        uuid4(),
        "cms.announcement_published",
        "system",
        "announcement",
        1,
        {"announcement_title": "更新"},
    )
    second = ns.page(u, "order", first["next_cursor"], 1)
    assert first["results"][0]["id"] != second["results"][0]["id"]
    result = ns.mark_read(u, {"type": "order", "watermark": second["read_watermark"]})
    assert result["updated_count"] == 3
    assert set(
        Notification.objects.filter(user=u, read_at__isnull=True).values_list(
            "pk", flat=True
        )
    ) == {new.pk, system.pk}


def test_default_address_contract():
    u = User.objects.create_user("address_buyer")
    Address.objects.create(user=u, **address_payload(is_default=True))
    one = Address.objects.create(user=u, **address_payload(is_default=False))
    # Capture the request issued by the actual mini page, then exercise its DRF endpoint.
    js = """
const fs=require('node:fs'),vm=require('node:vm');
let page, captured;
vm.runInNewContext(fs.readFileSync('mini/pages/addresses/addresses.js','utf8'),{
 Page:p=>page=p,require:()=>({request:async o=>{captured=o;return {}}})});
page.load=()=>{};page.setData=v=>Object.assign(page.data,v);
page.makeDefault({currentTarget:{dataset:{item:{id:process.argv[1],version:Number(process.argv[2])}}}})
.then(()=>console.log(JSON.stringify(captured)));
"""
    request = json.loads(
        subprocess.check_output(
            ["node", "-e", js, str(one.pk), str(one.version)],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
        )
    )
    res = getattr(client_for(u), request["method"].lower())(
        "/api/v1" + request["path"], request.get("data", {}), format="json"
    )
    print("mini_default_address_http=", res.status_code)
    assert res.status_code == 200
    client_for(u).post("/api/v1" + request["path"], request["data"], format="json")
    assert Address.objects.get(user=u, is_default=True).pk == one.pk


def test_historical_audit_search():
    from django.contrib.auth.models import Group
    from catalog.models import CatalogEvent, Category, Product

    u = User.objects.create_user("audit_buyer")
    u.groups.add(Group.objects.get(name="audit_viewer"))
    category = Category.objects.create(name="category")
    old = Product.objects.create(title="old", category=category)
    other = Product.objects.create(title="other", category=category)
    CatalogEvent.objects.create(product=old, actor=u, action="create", snapshot={})
    CatalogEvent.objects.bulk_create(
        [
            CatalogEvent(product=other, actor=u, action="edit", snapshot={})
            for _ in range(100)
        ]
    )
    response = client_for(u).get(
        f"/api/v1/ops/audits/?object_type=product&object_id={old.pk}"
    )
    assert response.status_code == 200, response.content
    assert response.data["data"]["count"] == 1

    unfiltered = client_for(u).get("/api/v1/ops/audits/?page_size=100&page=2")
    assert unfiltered.status_code == 200
    history = unfiltered.data["data"]
    assert history["count"] == 101 and history["total_pages"] == 2
    assert history["results"][0]["id"] == response.data["data"]["results"][0]["id"]
