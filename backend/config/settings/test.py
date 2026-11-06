"""测试环境配置：SQLite + 本地内存缓存，保证测试不依赖 MariaDB/Redis。"""

from .dev import *  # noqa: F401,F403

DEBUG = False  # 关闭 DEBUG 才能走到自定义 404/500 处理

ALLOWED_HOSTS = ["*"]  # 测试客户端使用 testserver 主机名

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mall-test",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LOGGING["root"]["handlers"] = ["console"]  # noqa: F405
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["handlers"]["console"]["formatter"] = "console"  # noqa: F405
