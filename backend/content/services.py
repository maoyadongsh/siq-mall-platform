import hashlib
import json
from html.parser import HTMLParser
from uuid import uuid4

import nh3
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from redis.exceptions import RedisError

from catalog.models import MediaAsset, Product
from common.constants import ErrorCode as Code
from common.exceptions import BusinessError

from .models import Content, ContentAction, ContentEvent, ContentRevision

KINDS = ("banner", "floor", "announcement", "page")
PLATFORMS = ("web", "mobile", "mini")
HOME_CACHE_KEY = "content:home:{platform}"
ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "a",
    "h2",
    "h3",
    "blockquote",
}
BLOCK_TYPES = {"heading", "text", "rich_text", "image", "link", "product_list"}


def invalid(message, status=400):
    raise BusinessError(Code.CONTENT_INVALID, message, http_status=status)


def conflict(message):
    raise BusinessError(Code.VERSION_CONFLICT, message, http_status=409)


class SafeHtmlParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            invalid(f"富文本不允许标签 {tag}")
        for name, value in attrs:
            if tag != "a" or name not in {"href", "title", "rel"}:
                invalid(f"富文本不允许属性 {name}")
            if name == "href":
                validate_link(value or "")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def validate_link(value):
    if not value or len(value) > 500 or any(ord(char) < 32 for char in value):
        invalid("链接为空或超出限制")
    if "\\" in value or value.startswith("//"):
        invalid("链接不在允许范围")
    if value.startswith("/"):
        return value
    if value.startswith("https://") and len(value) > 8:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if parsed.hostname and not parsed.username and not parsed.password:
            return value
    invalid("仅允许站内路径或HTTPS链接")


def clean_html(value):
    if not value or len(value) > 20000:
        invalid("富文本为空或超过20000字")
    parser = SafeHtmlParser(convert_charrefs=True)
    try:
        parser.feed(value)
        parser.close()
    except BusinessError:
        raise
    except Exception as exc:
        raise BusinessError(Code.CONTENT_INVALID, "富文本格式不完整") from exc
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes={"a": {"href", "title"}},
        url_schemes={"https"},
        link_rel="noopener noreferrer",
    )


def plain_text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        invalid(f"{label}必填且不能超过{maximum}字")
    return value.strip()


def validate_blocks(blocks, kind, require_products=False):
    if not isinstance(blocks, list) or not blocks or len(blocks) > 50:
        invalid("内容块数量为1–50")
    cleaned = []
    product_ids = set()
    for block in blocks:
        if not isinstance(block, dict) or set(block) - {
            "type",
            "text",
            "level",
            "html",
            "asset_id",
            "mobile_asset_id",
            "alt",
            "label",
            "url",
            "product_ids",
        }:
            invalid("内容块包含未知字段")
        block_type = block.get("type")
        if block_type not in BLOCK_TYPES:
            invalid("不支持跨端内容块类型")
        if block_type == "heading":
            level = block.get("level", 2)
            if level not in (1, 2, 3):
                invalid("标题层级仅支持1–3")
            cleaned.append(
                {
                    "type": block_type,
                    "text": plain_text(block.get("text"), "标题", 120),
                    "level": level,
                }
            )
        elif block_type == "text":
            cleaned.append(
                {
                    "type": block_type,
                    "text": plain_text(block.get("text"), "正文", 5000),
                }
            )
        elif block_type == "rich_text":
            cleaned.append(
                {"type": block_type, "html": clean_html(block.get("html", ""))}
            )
        elif block_type == "image":
            asset_id = block.get("asset_id")
            mobile_id = block.get("mobile_asset_id")
            if not isinstance(asset_id, int) or asset_id < 1:
                invalid("图片内容块缺少媒体ID")
            if mobile_id is not None and (
                not isinstance(mobile_id, int) or mobile_id < 1
            ):
                invalid("移动图片媒体ID无效")
            required_ids = {asset_id} | ({mobile_id} if mobile_id else set())
            assets = list(MediaAsset.objects.filter(pk__in=required_ids))
            if len(assets) != len(required_ids):
                invalid("图片媒体不存在或尚未就绪")
            cleaned.append(
                {
                    "type": block_type,
                    "asset_id": asset_id,
                    "mobile_asset_id": mobile_id,
                    "alt": plain_text(block.get("alt"), "图片替代文本", 120),
                }
            )
        elif block_type == "link":
            cleaned.append(
                {
                    "type": block_type,
                    "label": plain_text(block.get("label"), "链接文字", 80),
                    "url": validate_link(block.get("url", "")),
                }
            )
        else:
            ids = block.get("product_ids")
            if kind not in {"floor", "banner"} or not isinstance(ids, list):
                invalid("商品推荐仅用于首页楼层或Banner")
            if (
                not ids
                or len(ids) > 12
                or any(not isinstance(item, int) or item < 1 for item in ids)
            ):
                invalid("推荐商品为1–12个有效ID")
            if len(set(ids)) != len(ids):
                invalid("推荐商品不能重复")
            product_ids.update(ids)
            cleaned.append({"type": block_type, "product_ids": ids})
    if kind == "floor" and not any(
        block["type"] == "product_list" for block in cleaned
    ):
        invalid("首页楼层至少包含一个商品推荐块")
    if require_products and product_ids:
        available = set(
            Product.objects.filter(
                pk__in=product_ids,
                status=Product.Status.ON_SALE,
                skus__available_stock__gt=0,
            ).values_list("pk", flat=True)
        )
        if available != product_ids:
            invalid("推荐商品不存在、已下架或无可售库存")
    return cleaned


def validate_revision(data, kind, require_products=False):
    platforms = data["platforms"]
    if not platforms or set(platforms) - set(PLATFORMS):
        invalid("展示端必须选自web、mobile、mini")
    if len(set(platforms)) != len(platforms):
        invalid("展示端不能重复")
    end_at = data.get("end_at")
    if end_at and end_at <= data["start_at"]:
        invalid("结束时间必须晚于开始时间")
    notify_inbox = data.get("notify_inbox", False)
    if notify_inbox and kind != "announcement":
        invalid("只有公告可以联动站内通知")
    return {
        "title": plain_text(data["title"], "内容标题", 120),
        "blocks": validate_blocks(data["blocks"], kind, require_products),
        "platforms": platforms,
        "sort_order": data["sort_order"],
        "start_at": data["start_at"],
        "end_at": end_at,
        "notify_inbox": notify_inbox,
    }


def product_card(product):
    prices = [sku.price for sku in product.skus.all() if sku.available_stock > 0]
    return {
        "id": str(product.pk),
        "title": product.title,
        "cover_url": product.cover.file.url if product.cover_id else None,
        "min_price": str(min(prices)) if prices else None,
        "currency": "CNY",
        "sale_status": product.status,
    }


def hydrate_blocks(blocks, platform):
    product_ids = {
        item
        for block in blocks
        if block["type"] == "product_list"
        for item in block["product_ids"]
    }
    asset_ids = {
        item
        for block in blocks
        if block["type"] == "image"
        for item in (block["asset_id"], block.get("mobile_asset_id"))
        if item
    }
    products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=product_ids,
            status=Product.Status.ON_SALE,
            skus__available_stock__gt=0,
        )
        .select_related("cover")
        .prefetch_related("skus")
        .distinct()
    }
    assets = {asset.pk: asset for asset in MediaAsset.objects.filter(pk__in=asset_ids)}
    hydrated = []
    for block in blocks:
        if block["type"] == "product_list":
            cards = [
                product_card(products[product_id])
                for product_id in block["product_ids"]
                if product_id in products
            ]
            hydrated.append(
                {
                    "type": "product_list",
                    "product_ids": [int(card["id"]) for card in cards],
                    "products": cards,
                }
            )
        elif block["type"] == "image":
            asset_id = (
                block.get("mobile_asset_id")
                if platform in {"mobile", "mini"} and block.get("mobile_asset_id")
                else block["asset_id"]
            )
            asset = assets[asset_id]
            hydrated.append(
                {
                    "type": "image",
                    "asset_id": asset_id,
                    "url": asset.file.url,
                    "width": asset.width,
                    "height": asset.height,
                    "alt": block["alt"],
                }
            )
        else:
            hydrated.append(block)
    return hydrated


def revision_data(revision, platform="web", hydrate=False):
    return {
        "revision_no": revision.revision_no,
        "title": revision.title,
        "blocks": (
            hydrate_blocks(revision.blocks, platform) if hydrate else revision.blocks
        ),
        "platforms": revision.platforms,
        "sort_order": revision.sort_order,
        "start_at": revision.start_at.isoformat(),
        "end_at": revision.end_at.isoformat() if revision.end_at else None,
        "notify_inbox": revision.notify_inbox,
        "created_at": revision.created_at.isoformat(),
    }


def publication_state(content, now=None):
    now = now or timezone.now()
    if content.status == "draft":
        return "draft"
    if content.status == "offline" or not content.published_revision_id:
        return "offline"
    revision = content.published_revision
    if revision.start_at > now:
        return "scheduled"
    if revision.end_at and revision.end_at <= now:
        return "expired"
    return "online"


def content_data(content, include_revisions=False):
    latest = content.revisions.order_by("-revision_no").first()
    data = {
        "id": str(content.pk),
        "kind": content.kind,
        "slug": content.slug,
        "status": content.status,
        "publication_state": publication_state(content),
        "version": content.version,
        "published_revision": (
            content.published_revision.revision_no
            if content.published_revision_id
            else None
        ),
        "latest_revision": revision_data(latest),
    }
    if include_revisions:
        data["revisions"] = [
            revision_data(row)
            for row in content.revisions.order_by("-revision_no")[:50]
        ]
    return data


@transaction.atomic
def create_content(actor, data):
    kind = data["kind"]
    values = validate_revision(data, kind)
    slug = data.get("slug") or f"{kind}-{uuid4().hex[:12]}"
    if Content.objects.filter(slug=slug).exists():
        invalid("内容标识已存在")
    try:
        content = Content.objects.create(kind=kind, slug=slug)
    except IntegrityError as exc:
        raise BusinessError(Code.CONTENT_INVALID, "内容标识已存在") from exc
    revision = ContentRevision.objects.create(
        content=content, revision_no=1, editor=actor, **values
    )
    ContentAction.objects.create(
        actor=actor,
        content=content,
        revision=revision,
        operation="create",
        snapshot={"version": content.version},
    )
    return content_data(content, True)


@transaction.atomic
def revise_content(actor, pk, data):
    content = get_object_or_404(Content.objects.select_for_update(), pk=pk)
    if content.version != data["expected_version"]:
        conflict("内容已更新，请刷新后核对")
    if data.get("slug") and data["slug"] != content.slug:
        invalid("内容标识用于公开链接，创建后不可修改")
    values = validate_revision(data, content.kind)
    revision = ContentRevision.objects.create(
        content=content,
        revision_no=content.revisions.count() + 1,
        editor=actor,
        **values,
    )
    content.version += 1
    content.save(update_fields=["version", "updated_at"])
    ContentAction.objects.create(
        actor=actor,
        content=content,
        revision=revision,
        operation="revise",
        snapshot={"version": content.version},
    )
    return content_data(content, True)


def digest(parts):
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def invalidate_home():
    for platform in PLATFORMS:
        try:
            cache.delete(HOME_CACHE_KEY.format(platform=platform))
        except RedisError:
            continue


@transaction.atomic
def change_publication(actor, pk, data, action_key, publish):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().only("pk").get(pk=actor.pk)
    operation = "publish" if publish else "unpublish"
    request_digest = digest([str(pk), data, publish])
    prior = ContentAction.objects.filter(
        actor=actor, operation=operation, key=action_key
    ).first()
    if prior:
        if prior.digest != request_digest:
            raise BusinessError(
                Code.IDEMPOTENCY_CONFLICT,
                "提交标识已用于其他内容或版本",
                http_status=409,
            )
        return prior.result
    content = get_object_or_404(
        Content.objects.select_for_update().select_related("published_revision"), pk=pk
    )
    if content.version != data["expected_version"]:
        conflict("内容已更新，请刷新后核对")
    revision = get_object_or_404(
        ContentRevision, content=content, revision_no=data["revision"]
    )
    if publish:
        validate_revision(revision_data(revision), content.kind, True)
        content.published_revision = revision
        content.status = "published"
        if content.kind == "announcement" and revision.notify_inbox:
            ContentEvent.objects.get_or_create(revision=revision)
    else:
        if (
            content.published_revision_id != revision.pk
            or content.status != "published"
        ):
            raise BusinessError(
                Code.CONTENT_STATE_INVALID, "当前内容未启用该发布版本", http_status=409
            )
        content.status = "offline"
    content.version += 1
    content.save(
        update_fields=["published_revision", "status", "version", "updated_at"]
    )
    result = content_data(content, True)
    ContentAction.objects.create(
        actor=actor,
        content=content,
        revision=revision,
        operation=operation,
        key=action_key,
        digest=request_digest,
        reason=data["reason"],
        snapshot={"version": content.version},
        result=result,
    )
    transaction.on_commit(invalidate_home)
    return result


def active_content(row, platform, now):
    revision = row.published_revision
    return (
        row.status == "published"
        and revision is not None
        and platform in revision.platforms
        and revision.start_at <= now
        and (revision.end_at is None or revision.end_at > now)
    )


def public_rows(platform, now):
    rows = (
        Content.objects.filter(kind__in={"banner", "floor", "announcement"})
        .select_related("published_revision")
        .order_by("published_revision__sort_order", "id")
    )
    return [row for row in rows if active_content(row, platform, now)]


def public_home(platform):
    now = timezone.now()
    cache_key = HOME_CACHE_KEY.format(platform=platform)
    try:
        cached = cache.get(cache_key)
    except RedisError:
        cached = None
    if cached is None:
        rows = public_rows(platform, now)
        cached = [
            {
                "id": str(row.pk),
                "kind": row.kind,
                "slug": row.slug,
                "title": row.published_revision.title,
                "revision_no": row.published_revision.revision_no,
                "blocks": row.published_revision.blocks,
            }
            for row in rows
        ]
        try:
            cache.set(cache_key, cached, timeout=60)
        except RedisError:
            pass
    result = {"banners": [], "floors": [], "announcements": []}
    for row in cached:
        item = {**row, "blocks": hydrate_blocks(row["blocks"], platform)}
        result[
            f"{row['kind']}s" if row["kind"] != "announcement" else "announcements"
        ].append(item)
    result["platform"] = platform
    result["fallback_products"] = []
    if not any(result[key] for key in ("banners", "floors", "announcements")):
        products = (
            Product.objects.filter(
                status=Product.Status.ON_SALE, skus__available_stock__gt=0
            )
            .select_related("cover")
            .prefetch_related("skus")
            .order_by("-id")
            .distinct()[:12]
        )
        result["fallback_products"] = [product_card(product) for product in products]
    return result


def public_detail(kind, identifier, platform="web"):
    rows = Content.objects.select_related("published_revision")
    if kind == "announcement":
        row = get_object_or_404(rows, kind=kind, pk=identifier)
    else:
        row = get_object_or_404(rows, kind=kind, slug=identifier)
    if not active_content(row, platform, timezone.now()):
        raise Http404
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "slug": row.slug,
        "revision": revision_data(row.published_revision, platform, True),
    }


def preview(user, pk, revision_no, platform):
    row = get_object_or_404(Content, pk=pk)
    revision = get_object_or_404(ContentRevision, content=row, revision_no=revision_no)
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "slug": row.slug,
        "platform": platform,
        "preview": True,
        "revision": revision_data(revision, platform, True),
    }
