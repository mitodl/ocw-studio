"""
As described in
http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html
"""

import logging
import os
import time

from celery import Celery
from celery.signals import before_task_publish, task_postrun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

log = logging.getLogger(__name__)

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
    "content_sync.tasks.trigger_mass_build": {"queue": "batch"},
    "content_sync.tasks.publish_website_batch": {"queue": "batch"},
    "content_sync.tasks.publish_websites": {"queue": "batch"},
    "external_resources.tasks.check_external_resources": {"queue": "batch"},
}


@before_task_publish.connect
def timestamp_task_send(
    headers=None,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """Before a task is sent, timestamp the task with the current time"""
    headers.setdefault("task_sent_timestamp", time.time())


@task_postrun.connect
def log_task_deltatime(
    task=None,
    state=None,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """If the task provided a timestamp for which it was sent, log timing information"""
    # Note: you'd think headers would come in on `task.request.headers` but you'd be wrong  # noqa: E501
    try:
        task_sent_timestamp = getattr(task.request, "task_sent_timestamp", None)
        task_id = task.request.id
        task_name = task.request.task

        if task_sent_timestamp:
            task_postrun_timestamp = time.time()
            task_deltatime = task_postrun_timestamp - task_sent_timestamp
            # ignore deltas below zero in case of clock drift
            task_deltatime = max(task_deltatime, 0)

            log.info(
                "task_event=log_task_deltatime "
                "task_name=%s task_id=%s task_state=%s "
                "task_sent_timestamp=%s task_postrun_timstamp=%s "
                "task_deltatime=%s",
                task_name,
                task_id,
                state,
                task_sent_timestamp,
                task_postrun_timestamp,
                task_deltatime,
            )
        else:
            log.error(
                "Task had no task_sent_timestamp: name=%s id=%s ", task_name, task_id
            )
    except:  # pylint: disable=bare-except  # noqa: E722
        log.exception("Unexpected error trying to log task deltatime")
