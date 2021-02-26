""" API functionality for OCW course site import """
import json
import logging
import os
import re
from uuid import uuid4

import yaml
from dateutil import parser as dateparser

from main.s3_utils import get_s3_object_and_read, get_s3_resource
from websites.constants import (
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    COURSE_HOME,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.models import Website, WebsiteContent


log = logging.getLogger(__name__)


def fetch_ocw2hugo_course_paths(bucket_name, prefix="", filter_str=""):
    """
    Generator that yields the path to every course JSON document in the S3 bucket matching
    a prefix and filter (or all of them if no prefix or filter is provided)

    Args:
        bucket_name (str): S3 bucket name
        prefix (str): (Optional) S3 prefix before start of course_id path
        filter_str (str): (Optional) If specified, only yield course paths containing this string

    Yields:
        str: The path to a course JSON document in S3
    """
    s3 = get_s3_resource()
    bucket = s3.Bucket(bucket_name)
    paginator = bucket.meta.client.get_paginator("list_objects")
    for resp in paginator.paginate(Bucket=bucket.name, Prefix=f"{prefix}data/courses/"):
        for obj in resp["Contents"]:
            key = obj["Key"]
            if key.endswith(".json") and (not filter_str or filter_str in key):
                yield key


def import_ocw2hugo_content(bucket, prefix, website):  # pylint:disable=too-many-locals
    """
    Import all content files for an ocw course from hugo2ocw output

    Args:
        bucket (s3.Bucket): S3 bucket
        prefix (str): S3 prefix for filtering by course
        website (Website): Website to import content for
    """
    for resp in bucket.meta.client.get_paginator("list_objects").paginate(
        Bucket=bucket.name, Prefix=f"{prefix}content/courses/{website.name}"
    ):
        for obj in resp["Contents"]:
            s3_key = obj["Key"]
            s3_content = get_s3_object_and_read(bucket.Object(s3_key)).decode()
            s3_content_parts = [
                part
                for part in re.split(re.compile(r"^---\n", re.MULTILINE), s3_content)
                if part
            ]
            parent = None
            if len(s3_content_parts) >= 1:
                content_json = yaml.load(s3_content_parts[0], Loader=yaml.Loader)
                menu = content_json.get("menu", None)
                if menu:
                    # This is a page
                    menu_values = list(menu.values())[0]
                    uuid = menu_values.get("identifier")
                    if uuid == COURSE_HOME:
                        uuid = website.uuid
                    parent_uuid = menu_values.get("parent", None)
                    content_type = CONTENT_TYPE_PAGE
                else:
                    # This is a file
                    uuid = content_json.get("uid")
                    parent_uuid = content_json.get("parent", None)
                    content_type = CONTENT_TYPE_RESOURCE
                if parent_uuid:
                    parent, _ = WebsiteContent.objects.get_or_create(
                        website=website, uuid=parent_uuid
                    )
                filepath = obj["Key"].replace(prefix, "")
                base_defaults = {
                    "metadata": content_json,
                    "markdown": (
                        s3_content_parts[1] if len(s3_content_parts) == 2 else None
                    ),
                    "parent": parent,
                    "title": content_json.get("title"),
                    "type": content_type,
                }
                try:
                    if not uuid:
                        # create a new uuid if necessary
                        WebsiteContent.objects.update_or_create(
                            website=website,
                            hugo_filepath=filepath,
                            defaults={**base_defaults, "uuid": uuid4()},
                        )
                    else:
                        WebsiteContent.objects.update_or_create(
                            website=website,
                            uuid=uuid,
                            defaults={**base_defaults, "hugo_filepath": filepath},
                        )
                except:  # pylint:disable=bare-except
                    log.exception("Error saving WebsiteContent for %s", s3_key)


def import_ocw2hugo_course(bucket_name, prefix, path, starter_id=None):
    """
    Extract OCW course content for a course

    Args:
        bucket_name (str): An s3 bucket name
        prefix (str): S3 prefix before start of course_id path
        path (str): The course URL path
        starter_id (int or None): The id of the WebsiteStarter to associated with the created Website
    """
    s3 = get_s3_resource()
    bucket = s3.Bucket(bucket_name)
    name = os.path.splitext(os.path.basename(path))[0]
    s3_content = json.loads(get_s3_object_and_read(bucket.Object(path)).decode())
    try:
        publish_date = dateparser.parse(s3_content.get("publishdate", None))
    except ValueError:
        publish_date = None
        s3_content["publishdate"] = None
    try:
        website, _ = Website.objects.update_or_create(
            name=name,
            defaults={
                "title": s3_content.get("course_title", f"Course Site ({name})"),
                "publish_date": publish_date,
                "metadata": s3_content,
                "starter_id": starter_id,
                "source": WEBSITE_SOURCE_OCW_IMPORT,
            },
        )
        import_ocw2hugo_content(bucket, prefix, website)
    except:  # pylint:disable=bare-except
        log.exception("Error saving website %s", path)
