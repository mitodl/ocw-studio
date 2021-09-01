""" Tasks for OCW course site import """
import logging

import celery
from django.conf import settings
from mitol.common.utils.collections import chunks

from main.celery import app
from ocw_import.api import (
    delete_unpublished_courses,
    fetch_ocw2hugo_course_paths,
    import_ocw2hugo_course,
)
from websites.constants import WEBSITE_SOURCE_OCW_IMPORT
from websites.models import Website, WebsiteStarter


log = logging.getLogger(__name__)


@app.task()
def import_ocw2hugo_course_paths(
    paths=None, bucket_name=None, prefix=None
):
    """
    Import all ocw2hugo courses & content

    Args:
        paths (list of str): list of course url paths
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


@app.task(bind=True)
def import_ocw2hugo_courses(
    self, bucket_name=None, prefix=None, filter_str=None, limit=None, chunk_size=100
):  # pylint:disable=too-many-arguments
    """
    Import all ocw2hugo courses & content

    Args:
        bucket_name (str): S3 bucket name
        prefix (str): (Optional) S3 prefix before start of course_id path
        filter_str (str): (Optional) If specified, only yield course paths containing this string
        limit (int or None): (Optional) If specified, limits the number of courses imported
        chunk_size (int): Number of courses to process per task
    """
    if not bucket_name:
        raise TypeError("Bucket name must be specified")
    course_paths = iter(
        fetch_ocw2hugo_course_paths(bucket_name, prefix=prefix, filter_str=filter_str)
    )
    if delete_unpublished:
        course_ids = list(map((lambda key: key.replace("/data/course.json", "", 1)), course_paths))
        unpublished_courses = Website.objects.filter(
            source=WEBSITE_SOURCE_OCW_IMPORT
        ).exclude(name__in=course_ids)
        delete_unpublished_courses_tasks = 
    else:
        unpublished_courses = None
    if limit is not None:
        course_paths = (path for i, path in enumerate(course_paths) if i < limit)
    course_tasks = celery.group(
        [
            import_ocw2hugo_course_paths.si(
                paths=paths,
                bucket_name=bucket_name,
                prefix=prefix,
                filter_str=filter_str,
                delete_unpublished=delete_unpublished,
                unpublished_courses=unpublished_courses
            )
            for paths in chunks(course_paths, chunk_size=chunk_size)
        ]
    )
    raise self.replace(course_tasks)
