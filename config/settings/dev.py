from .base import *

DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

# Logs SQL en dev
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            # "level": "DEBUG",
        },
    },
}