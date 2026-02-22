"""
Celery task definitions.

Currently contains a placeholder for future CRM API integration.
The worker is not started by default — only the web process runs on Railway.
To start a worker: celery -A app.tasks worker --loglevel=info
"""

import os

from celery import Celery

celery_app = Celery(
    "traffic_checker",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_app.task
def pull_from_crm():
    """
    Placeholder: pull leads from CRM API and upsert into DB.
    Not yet implemented — requires CRM API credentials and endpoint config.
    """
    raise NotImplementedError("CRM pull not yet implemented")
