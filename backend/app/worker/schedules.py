"""Celery Beat schedule definitions for periodic background maintenance and refresh."""

CELERY_BEAT_SCHEDULE = {
    "maintenance-stale-job-cleanup-every-5-mins": {
        "task": "maintenance.cleanup",
        "schedule": 300.0,  # Every 5 minutes
        "args": (),
    },
    "price-refresh-periodic": {
        "task": "price.refresh",
        "schedule": 3600.0,  # Every hour
        "args": (),
    },
}

