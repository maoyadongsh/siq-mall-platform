"""媒体存储入口：本地 FileSystemStorage 与可选的云存储共用同一接口。"""

from django.core.files.storage import default_storage


def media_url(name: str | None) -> str | None:
    if not name:
        return None
    return default_storage.url(name)


def media_exists(name: str) -> bool:
    return bool(name) and default_storage.exists(name)
