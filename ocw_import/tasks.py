""" Tasks for OCW course site import """
import logging

import celery
from django.conf import settings
from mitol.common.utils.collections import chunks

from main.celery import app
from main.tasks import chord_finisher
from ocw_import.api import (
    fetch_ocw2hugo_course_paths,
    import_ocw2hugo_course,
    update_ocw2hugo_course,
)
from websites.constants import WEBSITE_SOURCE_OCW_IMPORT
from websites.models import Website, WebsiteStarter


log = logging.getLogger(__name__)


@app.task()
def import_ocw2hugo_course_paths(paths=None, bucket_name=None, prefix=None):
    """
    Import all ocw2hugo courses & content

    Args:
        paths (list of str): list of course data template paths
        bucket_name (str): S3 bucket name
        prefix (str): S3 prefix before start of course_id path
    """
    if not paths:
        return
    course_site_starter_id = (
        WebsiteStarter.objects.filter(slug=settings.OCW_IMPORT_STARTER_SLUG)
        .values_list("id", flat=True)
        .get()
    )
    for path in paths:
        log.info("Importing course: '%s'", path)
        import_ocw2hugo_course(
            bucket_name, prefix, path, starter_id=course_site_starter_id
        )


@app.task()
def update_ocw2hugo_course_paths(
    paths, bucket_name, prefix, content_field, create_new_content=False
):
    """
    Import all ocw2hugo courses & content

    Args:
        paths (list of str): list of course data template paths
        bucket_name (str): S3 bucket name
        prefix (str): S3 prefix before start of course_id path
    """
    if not paths:
        return

    for path in paths:
        log.info("Importing course: '%s'", path)
        update_ocw2hugo_course(
            bucket_name,
            prefix,
            path,
            content_field,
            create_new_content=create_new_content,
        )


@app.task(bind=True)
def import_ocw2hugo_courses(
    self,
    bucket_name=None,
    course_paths=None,
    prefix=None,
    limit=None,
    chunk_size=100,
):  # pylint:disable=too-many-arguments
    """
    Import all ocw2hugo courses & content

    Args:
        bucket_name (str): S3 bucket name
        course_paths (list of str): The paths of the courses to be imported
        prefix (str): (Optional) S3 prefix before start of course_id path
        limit (int): (Optional) Only import this amount of courses
        chunk_size (int): Number of courses to process per task
    """
    if not bucket_name:
        raise TypeError("Bucket name must be specified")
    if not course_paths:
        raise TypeError("Course paths must be specified")
    if limit is not None:
        course_paths = course_paths[:limit]
    course_tasks = [
        import_ocw2hugo_course_paths.si(
            paths=paths,
            bucket_name=bucket_name,
            prefix=prefix,
        )
        for paths in chunks(course_paths, chunk_size=chunk_size)
    ]
    import_steps = celery.chord(celery.group(course_tasks), chord_finisher.si())
    raise self.replace(celery.group(import_steps))


@app.task(bind=True)
def update_ocw_resource_data(
    self,
    bucket_name=None,
    prefix=None,
    filter_list=None,
    limit=None,
    chunk_size=100,
    content_field=None,
    create_new_content=False,
):  # pylint:disable=too-many-arguments
    """
    Import all ocw2hugo courses & content

    Args:
        bucket_name (str): S3 bucket name
        prefix (str): (Optional) S3 prefix before start of course_id path
        filter_list (List of str): (Optional) If specified, only yield course paths in this list of strings
        limit (int or None): (Optional) If specified, limits the number of courses imported
        chunk_size (int): Number of courses to process per task
        content_field(str): WebsiteContent field that should be updated
    """
    if not bucket_name:
        raise TypeError("Bucket name must be specified")

    if not content_field and not create_new_content:
        raise TypeError("Update field must be specified if create_new_content is False")
    course_paths = list(
        fetch_ocw2hugo_course_paths(bucket_name, prefix=prefix, filter_list=filter_list)
    )
    if limit is not None:
        course_paths = course_paths[:limit]
    course_tasks = [
        update_ocw2hugo_course_paths.si(
            paths=paths,
            bucket_name=bucket_name,
            prefix=prefix,
            content_field=content_field,
            create_new_content=create_new_content,
        )
        for paths in chunks(course_paths, chunk_size=chunk_size)
    ]

    raise self.replace(celery.group(course_tasks))
