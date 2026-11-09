from django.db import transaction
from django.shortcuts import get_object_or_404

from common.constants import ErrorCode
from common.exceptions import BusinessError

from .models import Category, CategoryEvent


def category_data(row):
    return {
        "id": str(row.pk),
        "name": row.name,
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "sort_order": row.sort_order,
        "enabled": row.enabled,
        "version": row.version,
    }


def tree(enabled_only=False):
    rows = (
        Category.objects.filter(enabled=True)
        if enabled_only
        else Category.objects.all()
    )
    nodes = {row.pk: {**category_data(row), "children": []} for row in rows}
    roots = []
    for row in rows.order_by("sort_order", "id"):
        if row.parent_id is None:
            roots.append(nodes[row.pk])
        elif row.parent_id in nodes:
            nodes[row.parent_id]["children"].append(nodes[row.pk])
    return roots


def descendants(category):
    rows = list(Category.objects.filter(enabled=True).values("id", "parent_id"))
    children = {}
    for row in rows:
        children.setdefault(row["parent_id"], []).append(row["id"])
    found = {category.pk}
    pending = [category.pk]
    while pending:
        current = pending.pop()
        for child in children.get(current, []):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def validate_parent(parent, category=None):
    seen = set()
    while parent:
        if parent.pk == getattr(category, "pk", None) or parent.pk in seen:
            raise BusinessError(ErrorCode.INVALID_PARAM, "分类父子关系不能成环")
        seen.add(parent.pk)
        parent = parent.parent


@transaction.atomic
def save_category(actor, data, pk=None):
    category = (
        get_object_or_404(Category.objects.select_for_update(), pk=pk)
        if pk
        else Category()
    )
    if pk and category.version != data["expected_version"]:
        raise BusinessError(
            ErrorCode.VERSION_CONFLICT, "分类已更新，请刷新后核对", http_status=409
        )
    parent = (
        get_object_or_404(Category, pk=data["parent_id"])
        if data.get("parent_id")
        else None
    )
    validate_parent(parent, category)
    if (
        Category.objects.exclude(pk=pk)
        .filter(name__iexact=data["name"].strip())
        .exists()
    ):
        raise BusinessError(ErrorCode.INVALID_PARAM, "分类名称已存在")
    category.name = data["name"].strip()
    category.parent = parent
    category.sort_order = data["sort_order"]
    category.enabled = data["enabled"]
    if pk:
        category.version += 1
    category.save()
    CategoryEvent.objects.create(
        category=category,
        actor=actor,
        action="update" if pk else "create",
        snapshot=category_data(category),
    )
    return category_data(category)
