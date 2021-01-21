""" Tasks for websites """
import logging

import celery

from main.celery import app
from main.utils import chunks
from websites.api import import_ocw2hugo_course, fetch_ocw2hugo_course_paths

log = logging.getLogger(__name__)


@app.task()
def import_ocw2hugo_course_paths(paths=None, bucket_name=None, prefix=None):
    """
    Import all ocw2hugo courses & content

    Args:
        paths (list): list of course url paths
        bucket_name (str): S3 bucket name
        prefix (str): S3 prefix before start of course_id path

    """
    if not paths:
        return
    for path in paths:
        log.info("Importing course: '%s'", path)
        import_ocw2hugo_course(bucket_name, prefix, path)


@app.task(bind=True)
def import_ocw2hugo_courses(
    self, bucket_name=None, prefix=None, filter_str=None, chunk_size=100
):
    """
    Import all ocw2hugo courses & content

    Args:
        bucket_name (str): S3 bucket name
        prefix (str): (Optional) S3 prefix before start of course_id path
        filter_str (str): (Optional) If specified, only yield course paths containing this string
        chunk_size (int): Number of courses to process per task
    """
    if not bucket_name:
        raise TypeError("Bucket name must be specified")
    course_paths = list(
        fetch_ocw2hugo_course_paths(bucket_name, prefix=prefix, filter_str=filter_str)
    )
    course_tasks = celery.group(
        [
            import_ocw2hugo_course_paths.si(
                paths=paths, bucket_name=bucket_name, prefix=prefix
            )
            for paths in chunks(course_paths, chunk_size=chunk_size)
        ]
    )
    raise self.replace(course_tasks)
