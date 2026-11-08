"""生产环境配置：Ubuntu 24.04 LTS，Nginx + Gunicorn（不容器化）。"""

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405  缺失即启动失败
ENVIRONMENT = env("DJANGO_ENV", "production")  # noqa: F405
DEMO_VERIFICATION_ENABLED = False
TERMS_VERSION = env("TERMS_VERSION", "demo-v1")  # noqa: F405

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "")  # noqa: F405
if not ALLOWED_HOSTS:
    raise RuntimeError("生产环境必须配置 ALLOWED_HOSTS")

# Nginx 终止 TLS，应用侧信任转发头
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = False  # 由 Nginx 统一 301，避免双重跳转
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

DATABASES["default"]["CONN_MAX_AGE"] = 120  # noqa: F405

CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = False  # noqa: F405

# 生产环境只接受白名单来源
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")  # noqa: F405

# 多个 Gunicorn worker 交由 journald 统一收集，避免文件轮转竞争。
LOGGING["handlers"].pop("file", None)  # noqa: F405
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
LOGGING["root"]["handlers"] = ["console"]  # noqa: F405
for logger_config in LOGGING["loggers"].values():  # noqa: F405
    logger_config["handlers"] = ["console"]
