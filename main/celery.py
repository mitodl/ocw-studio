"""
As described in
http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html
"""

import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("ocw_studio")

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.conf.task_default_queue = "default"
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "content_sync.tasks.sync_website_content": {"queue": "publish"},
    "content_sync.tasks.create_website_backend": {"queue": "publish"},
    "content_sync.tasks.publish_website_backend_draft": {"queue": "publish"},
    "content_sync.tasks.publish_website_backend_live": {"queue": "publish"},
    "content_sync.tasks.check_incomplete_publish_build_statuses": {"queue": "publish"},
    "content_sync.tasks.upsert_website_publishing_pipeline": {"queue": "publish"},
    "content_sync.tasks.sync_unsynced_websites": {"queue": "batch"},
    "content_sync.tasks.upsert_pipelines": {"queue": "batch"},
    "content_sync.tasks.trigger_mass_publish": {"queue": "batch"},
    "content_sync.tasks.publish_website_batch": {"queue": "batch"},
    "content_sync.tasks.publish_websites": {"queue": "batch"},
}
