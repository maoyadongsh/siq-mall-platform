from django.db import transaction

from common.constants import ErrorCode
from common.exceptions import BusinessError

from .models import Address


def not_found():
    return BusinessError(ErrorCode.NOT_FOUND, "地址不存在", http_status=404)


def check_version(address, expected_version):
    if address.version != expected_version:
        raise BusinessError(
            ErrorCode.VERSION_CONFLICT,
            "地址已被其他操作更新，请刷新后重试",
            http_status=409,
        )


def set_default(address):
    address.is_default = True
    address.version += 1
    address.save(update_fields=["is_default", "version", "updated_at"])


@transaction.atomic
def create_address(user, data):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().get(pk=user.pk)
    addresses = list(
        Address.objects.select_for_update().filter(user=user).order_by("id")
    )
    if len(addresses) >= 20:
        raise BusinessError(
            ErrorCode.ADDRESS_LIMIT_EXCEEDED, "最多保存20条地址", http_status=409
        )
    is_default = data.pop("is_default", False) or not addresses
    if is_default:
        for current in addresses:
            if current.is_default:
                current.is_default = False
                current.version += 1
                current.save(update_fields=["is_default", "version", "updated_at"])
    return Address.objects.create(user=user, is_default=is_default, **data)


@transaction.atomic
def update_address(user, address_id, data):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().get(pk=user.pk)
    expected_version = data.pop("expected_version")
    address = (
        Address.objects.select_for_update().filter(pk=address_id, user=user).first()
    )
    if address is None:
        raise not_found()
    check_version(address, expected_version)
    requested_default = data.pop("is_default", address.is_default)
    addresses = list(
        Address.objects.select_for_update().filter(user=user).exclude(pk=address.pk)
    )
    if requested_default:
        for current in addresses:
            if current.is_default:
                current.is_default = False
                current.version += 1
                current.save(update_fields=["is_default", "version", "updated_at"])
    elif address.is_default and addresses:
        replacement = max(addresses, key=lambda item: (item.updated_at, item.id))
        set_default(replacement)
    for field, value in data.items():
        setattr(address, field, value)
    address.is_default = requested_default
    address.version += 1
    address.save()
    return address


@transaction.atomic
def delete_address(user, address_id, expected_version):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().get(pk=user.pk)
    address = (
        Address.objects.select_for_update().filter(pk=address_id, user=user).first()
    )
    if address is None:
        raise not_found()
    check_version(address, expected_version)
    was_default = address.is_default
    address.delete()
    if was_default:
        replacement = (
            Address.objects.filter(user=user).order_by("-updated_at", "-id").first()
        )
        if replacement:
            set_default(replacement)


@transaction.atomic
def make_default(user, address_id):
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update().get(pk=user.pk)
    addresses = list(
        Address.objects.select_for_update().filter(user=user).order_by("id")
    )
    address = next((item for item in addresses if item.id == address_id), None)
    if address is None:
        raise not_found()
    if address.is_default:
        return address
    for current in addresses:
        if current.is_default:
            current.is_default = False
            current.version += 1
            current.save(update_fields=["is_default", "version", "updated_at"])
    set_default(address)
    return address
