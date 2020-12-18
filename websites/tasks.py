""" Tasks for websites """
import logging

import boto3
import celery
from django.conf import settings

from main.celery import app
from main.utils import chunks
from websites.utils import import_ocw2hugo_course

log = logging.getLogger(__name__)


@app.task(bind=True)
def import_ocw2hugo_course_paths(
    self, paths=None, bucket=None, prefix=None
):  # pylint:disable=unused-argument
    """
    Import all ocw2hugo courses & content

    Args:
        paths (list): list of course url paths
        bucket (str): S3 bucket name
        prefix (str): S3 prefix before start of course_id path

    """
    if not paths:
        return
    for path in paths:
        log.debug("Importing %s", path)
        import_ocw2hugo_course(bucket, prefix, path)


@app.task(bind=True)
def import_ocw2hugo_courses(self, bucket=None, prefix=None, chunk_size=100):
    """
    Import all ocw2hugo courses & content

    Args:
        bucket (str): S3 bucket name
        prefix (str): S3 prefix before start of course_id path
        chunk_size (int): Number of courses to process per task
    """
    if not bucket:
        raise TypeError("Bucket name must be specified")
    s3 = boto3.resource(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    bucket = s3.Bucket(bucket)
    course_paths = []
    paginator = bucket.meta.client.get_paginator("list_objects")
    for resp in paginator.paginate(Bucket=bucket.name, Prefix=f"{prefix}data/courses/"):
        for obj in resp["Contents"]:
            key = obj["Key"]
            if key.endswith(".json"):
                course_paths.append(key)
    course_tasks = celery.group(
        [
            import_ocw2hugo_course_paths.si(
                paths=paths, bucket=bucket.name, prefix=prefix
            )
            for paths in chunks(course_paths, chunk_size=chunk_size)
        ]
    )
    raise self.replace(course_tasks)
