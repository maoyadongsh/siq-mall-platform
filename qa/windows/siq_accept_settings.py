import os

from config.settings.test import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": "127.0.0.1",
        "PORT": int(os.environ["SIQ_TEST_PORT"]),
        "USER": "root",
        "PASSWORD": os.environ["SIQ_TEST_PASSWORD"],
        "NAME": "siq_accept",
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
CORS_ALLOWED_ORIGINS = [os.environ["SIQ_BROWSER_URL"]]
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")],
            "prefix": "mall:accept:channel",
        },
    }
}

DEBUG = True
MEDIA_ROOT = os.environ["SIQ_TEST_MEDIA_ROOT"]
