import os
import pymysql
from config.settings.test import *  # noqa: F403

pymysql.install_as_MySQLdb()
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
