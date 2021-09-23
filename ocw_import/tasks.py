""" Tasks for OCW course site import """
import logging

import celery
from django.conf import settings
from mitol.common.utils.collections import chunks

from main.celery import app
from ocw_import.api import fetch_ocw2hugo_course_paths, import_ocw2hugo_course
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
def delete_unpublished_courses(paths=None):
    """
    Delete all unpublished courses based on paths not present for existing Websites

    Args:
        paths: (list of str): list of course data template paths
    """
    if not paths:
        return
    course_ids = list(
        map((lambda key: key.replace("/data/course_legacy.json", "", 1)), paths)
    )
    unpublished_courses = Website.objects.filter(
        source=WEBSITE_SOURCE_OCW_IMPORT
    ).exclude(name__in=course_ids)
    if unpublished_courses.count() == 0:
        log.info("No unpublished courses to delete")
        return
    else:
        log.info("Deleting unpublished courses: %s", unpublished_courses)
        unpublished_courses.delete()


@app.task(bind=True)
def import_ocw2hugo_courses(
    self,
    bucket_name=None,
    prefix=None,
    filter_str=None,
    limit=None,
    delete_unpublished=True,
    chunk_size=100,
):  # pylint:disable=too-many-arguments
    """
    Import all ocw2hugo courses & content

    Args:
        bucket_name (str): S3 bucket name
        prefix (str): (Optional) S3 prefix before start of course_id path
        filter_str (str): (Optional) If specified, only yield course paths containing this string
        limit (int or None): (Optional) If specified, limits the number of courses imported
        delete_unpublished (bool): (Optional) If true, delete unpublished courses from the DB
        chunk_size (int): Number of courses to process per task
    """
    if not bucket_name:
        raise TypeError("Bucket name must be specified")
    course_paths = list(fetch_ocw2hugo_course_paths(bucket_name, prefix=prefix))
    if delete_unpublished:
        delete_unpublished_courses_task = delete_unpublished_courses.si(
            paths=course_paths
        )
    else:
        delete_unpublished_courses_task = None
    if filter_str is not None:
        course_paths = [path for path in course_paths if filter_str in path]
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
    if delete_unpublished_courses_task is not None:
        course_tasks.append(delete_unpublished_courses_task)
    raise self.replace(celery.group(course_tasks))
