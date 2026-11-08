"""开发环境配置：Windows 11。"""

import os

from .base import *  # noqa: F401,F403

DEBUG = True

# 开发环境允许无密钥启动；生产环境由 prod.py 强制要求 DJANGO_SECRET_KEY
SECRET_KEY = (
    os.getenv("DJANGO_SECRET_KEY") or "dev-only-insecure-key-do-not-use-in-production"
)

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]

ENVIRONMENT = "development"
DEMO_VERIFICATION_ENABLED = True
TERMS_VERSION = "demo-v1"

# 本地调试时不复用长连接，便于看到每次请求的真实连接状态
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

CORS_ALLOW_ALL_ORIGINS = False
