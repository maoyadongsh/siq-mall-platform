from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from catalog.models import Category, Product, Sku
from content.models import ContentAction


pytestmark = pytest.mark.django_db(transaction=True)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def operator(name="content_admin"):
    user = User.objects.create_user(name)
    user.groups.add(Group.objects.get(name="content_operator"))
    return user, client_for(user)


def payload(kind="page", **changes):
    data = {
        "kind": kind,
        "slug": "service-guide" if kind == "page" else "",
        "title": "服务指南",
        "blocks": [{"type": "text", "text": "真实内容"}],
        "platforms": ["web", "mobile", "mini"],
        "sort_order": 0,
        "start_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        "end_at": (timezone.now() + timedelta(days=1)).isoformat(),
    }
    data.update(changes)
    return data


def create(client, data):
    response = client.post("/api/v1/ops/cms/", data, format="json")
    assert response.status_code == 201, response.content
    return response.data["data"]


def revision_payload(content, **changes):
    revision = content["latest_revision"]
    data = {
        "expected_version": content["version"],
        "slug": content["slug"],
        "title": revision["title"],
        "blocks": revision["blocks"],
        "platforms": revision["platforms"],
        "sort_order": revision["sort_order"],
        "start_at": revision["start_at"],
        "end_at": revision["end_at"],
    }
    data.update(changes)
    return data


def publish(client, content, revision=1, action_key=None, action="publish"):
    data = {
        "revision": revision,
        "expected_version": content["version"],
        "reason": "验收发布" if action == "publish" else "验收下线",
    }
    response = client.post(
        f"/api/v1/ops/cms/{content['id']}/{action}/",
        data,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(action_key or uuid4()),
    )
    assert response.status_code == 200, response.content
    return response.data["data"]


def product(title="可售茶杯", status=Product.Status.ON_SALE, stock=3):
    row = Product.objects.create(
        category=Category.objects.create(name=title + "分类"),
        title=title,
        status=status,
    )
    Sku.objects.create(product=row, label="标准", price="99.00", available_stock=stock)
    return row


def test_draft_preview_publication_schedule_unpublish_and_fallback():
    sale = product()
    guest = APIClient()
    home = guest.get("/api/v1/cms/home/").data["data"]
    assert [row["id"] for row in home["fallback_products"]] == [str(sale.pk)]
    user, client = operator()
    ordinary = client_for(User.objects.create_user("ordinary_cms", is_staff=True))
    assert ordinary.get("/api/v1/ops/cms/").status_code == 403

    content = create(client, payload())
    detail_path = f"/api/v1/cms/pages/{content['slug']}/"
    assert guest.get(detail_path).status_code == 404
    preview = client.get(
        f"/api/v1/ops/cms/{content['id']}/preview/?revision=1&platform=mini"
    )
    assert preview.status_code == 200 and preview.data["data"]["preview"]
    assert (
        ordinary.get(f"/api/v1/ops/cms/{content['id']}/preview/?revision=1").status_code
        == 403
    )
    published = publish(client, content)
    assert published["publication_state"] == "online"
    assert guest.get(detail_path).data["data"]["revision"]["title"] == "服务指南"

    response = client.patch(
        f"/api/v1/ops/cms/{content['id']}/draft/",
        revision_payload(published, title="未发布草稿"),
        format="json",
    )
    assert response.status_code == 200, response.content
    drafted = response.data["data"]
    assert guest.get(detail_path).data["data"]["revision"]["title"] == "服务指南"
    assert (
        client.get(f"/api/v1/ops/cms/{content['id']}/preview/?revision=2").data["data"][
            "revision"
        ]["title"]
        == "未发布草稿"
    )
    second = publish(client, drafted, revision=2)
    assert guest.get(detail_path).data["data"]["revision"]["title"] == "未发布草稿"
    offline = publish(client, second, revision=2, action="unpublish")
    assert offline["publication_state"] == "offline"
    assert guest.get(detail_path).status_code == 404
    assert ContentAction.objects.filter(content_id=content["id"]).count() == 5

    future = timezone.now() + timedelta(hours=1)
    scheduled = create(
        client,
        payload(
            kind="banner",
            title="定时Banner",
            start_at=future.isoformat(),
            end_at=(future + timedelta(hours=2)).isoformat(),
        ),
    )
    publish(client, scheduled)
    assert guest.get("/api/v1/cms/home/").data["data"]["banners"] == []
    with patch(
        "content.services.timezone.now", return_value=future + timedelta(seconds=1)
    ):
        cache.clear()
        banners = guest.get("/api/v1/cms/home/").data["data"]["banners"]
        assert [row["title"] for row in banners] == ["定时Banner"]
    with patch(
        "content.services.timezone.now", return_value=future + timedelta(hours=3)
    ):
        cache.clear()
        assert guest.get("/api/v1/cms/home/").data["data"]["banners"] == []


def test_recommendations_revalidated_against_product_state_even_with_cached_cms():
    sale = product("推荐茶杯")
    off = product("下架茶杯", Product.Status.OFF_SALE)
    _, client = operator()
    content = create(
        client,
        payload(
            kind="floor",
            title="精选",
            blocks=[
                {"type": "heading", "text": "精选", "level": 2},
                {"type": "product_list", "product_ids": [sale.pk, off.pk]},
            ],
        ),
    )
    rejected = client.post(
        f"/api/v1/ops/cms/{content['id']}/publish/",
        {"revision": 1, "expected_version": 1, "reason": "含下架"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert rejected.status_code == 400 and rejected.data["code"] == 90004
    revised = client.patch(
        f"/api/v1/ops/cms/{content['id']}/draft/",
        revision_payload(
            content,
            blocks=[{"type": "product_list", "product_ids": [sale.pk]}],
        ),
        format="json",
    ).data["data"]
    publish(client, revised, revision=2)
    guest = APIClient()
    floor = guest.get("/api/v1/cms/home/").data["data"]["floors"][0]
    assert floor["blocks"][0]["products"][0]["title"] == "推荐茶杯"
    Product.objects.filter(pk=sale.pk).update(status=Product.Status.OFF_SALE)
    floor = guest.get("/api/v1/cms/home/").data["data"]["floors"][0]
    assert floor["blocks"][0]["products"] == []
    assert floor["blocks"][0]["product_ids"] == []


def test_rich_text_whitelist_links_and_content_media_upload():
    _, client = operator()
    for html in (
        '<p onclick="alert(1)">危险</p>',
        "<script>alert(1)</script><p>危险</p>",
        '<p><a href="javascript:alert(1)">危险</a></p>',
    ):
        response = client.post(
            "/api/v1/ops/cms/",
            payload(blocks=[{"type": "rich_text", "html": html}]),
            format="json",
        )
        assert response.status_code == 400 and response.data["code"] == 90004
    unsafe_link = payload(
        blocks=[{"type": "link", "label": "危险", "url": "//evil.example"}]
    )
    assert (
        client.post("/api/v1/ops/cms/", unsafe_link, format="json").status_code == 400
    )

    content = create(
        client,
        payload(
            blocks=[
                {
                    "type": "rich_text",
                    "html": '<p><strong>安全</strong><a href="https://example.com">链接</a></p>',
                }
            ]
        ),
    )
    publish(client, content)
    html = (
        APIClient()
        .get(f"/api/v1/cms/pages/{content['slug']}/")
        .data["data"]["revision"]["blocks"][0]["html"]
    )
    assert "<strong>安全</strong>" in html
    assert 'rel="noopener noreferrer"' in html
    assert "javascript:" not in html and "onclick" not in html

    fake = client.post(
        "/api/v1/ops/media/", {"file": BytesIO(b"not an image")}, format="multipart"
    )
    assert fake.status_code == 400
    image = BytesIO()
    Image.new("RGB", (20, 10), "green").save(image, format="PNG")
    image.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = client.post(
        "/api/v1/ops/media/",
        {
            "file": SimpleUploadedFile(
                "banner.png", image.read(), content_type="image/png"
            )
        },
        format="multipart",
    )
    assert upload.status_code == 201, upload.content
    asset = upload.data["data"]
    banner = create(
        client,
        payload(
            kind="banner",
            title="图片Banner",
            blocks=[
                {"type": "image", "asset_id": int(asset["asset_id"]), "alt": "茶杯"}
            ],
        ),
    )
    publish(client, banner)
    block = (
        APIClient()
        .get("/api/v1/cms/home/?platform=mobile")
        .data["data"]["banners"][0]["blocks"][0]
    )
    assert block["url"].endswith(".webp") and block["width"] == 20


def test_publication_replay_conflicts_audit_and_duplicate_slug():
    user, client = operator()
    content = create(client, payload())
    action_key = uuid4()
    data = {"revision": 1, "expected_version": 1, "reason": "首次"}
    path = f"/api/v1/ops/cms/{content['id']}/publish/"
    first = client.post(path, data, format="json", HTTP_IDEMPOTENCY_KEY=str(action_key))
    replay = client.post(
        path, data, format="json", HTTP_IDEMPOTENCY_KEY=str(action_key)
    )
    assert first.data["data"] == replay.data["data"]
    assert ContentAction.objects.filter(operation="publish").count() == 1
    conflict = client.post(
        path,
        {**data, "expected_version": 2},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(action_key),
    )
    assert conflict.status_code == 409
    stale = client.post(
        path,
        {**data, "expected_version": 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert stale.status_code == 409
    assert ContentAction.objects.filter(content_id=content["id"]).count() == 2
    duplicate = client.post("/api/v1/ops/cms/", payload(), format="json")
    assert duplicate.status_code == 400 and duplicate.data["code"] == 90004
    unknown = client.patch(
        f"/api/v1/ops/cms/{content['id']}/draft/",
        {**revision_payload(content), "status": "published"},
        format="json",
    )
    assert unknown.status_code == 400


def test_announcement_public_detail_and_mini_platform_visibility():
    _, client = operator()
    content = create(
        client,
        payload(kind="announcement", title="维护公告", platforms=["mini"]),
    )
    publish(client, content)
    path = f"/api/v1/cms/announcements/{content['id']}/"
    assert APIClient().get(path).status_code == 404
    response = APIClient().get(path + "?platform=mini")
    assert response.status_code == 200
    assert response.data["data"]["revision"]["title"] == "维护公告"
    home = APIClient().get("/api/v1/cms/home/?platform=mini").data["data"]
    assert [row["title"] for row in home["announcements"]] == ["维护公告"]


def test_announcement_inbox_event_is_optional_and_delivered_once_per_user():
    _, client = operator()
    from content.models import ContentEvent
    from notifications.models import Notification
    from notifications.services import deliver_content_event

    rejected = client.post(
        "/api/v1/ops/cms/",
        payload(kind="banner", notify_inbox=True),
        format="json",
    )
    assert rejected.status_code == 400
    content = create(
        client,
        payload(kind="announcement", title="需要通知的公告", notify_inbox=True),
    )
    published = publish(client, content)
    event = ContentEvent.objects.get(revision__content_id=content["id"])
    assert deliver_content_event(event.pk)
    assert not deliver_content_event(event.pk)
    recipients = User.objects.filter(is_active=True).count()
    assert Notification.objects.filter(event_id=event.event_id).count() == recipients
    assert set(
        Notification.objects.filter(event_id=event.event_id).values_list(
            "target_type", "target_id"
        )
    ) == {("announcement", content["id"])}
    republished = client.post(
        f"/api/v1/ops/cms/{content['id']}/publish/",
        {"revision": 1, "expected_version": published["version"], "reason": "重发检查"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert republished.status_code == 200
    assert ContentEvent.objects.count() == 1
    assert not deliver_content_event(event.pk)
    assert Notification.objects.filter(event_id=event.event_id).count() == recipients
