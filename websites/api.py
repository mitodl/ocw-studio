""" api functions for websites"""
import json
import os
import re
import logging
from uuid import uuid4

import yaml

from main.s3_utils import get_s3_object_and_read, get_s3_resource
from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_FILE, COURSE_HOME
from websites.models import Website, WebsiteContent

log = logging.getLogger(__name__)


def import_ocw2hugo_content(bucket, prefix, website):  # pylint:disable=too-many-locals
    """
    Import all content files for an ocw course from hugo2ocw output

    Args:
        bucket (s3.Bucket): S3 bucket
        prefix (str): S3 prefix for filtering by course
        website (Website): Website to import content for
    """
    for resp in bucket.meta.client.get_paginator("list_objects").paginate(
        Bucket=bucket.name, Prefix=f"{prefix}content/courses/{website.url_path}"
    ):
        for obj in resp["Contents"]:
            s3_content = get_s3_object_and_read(bucket.Object(obj["Key"])).decode()
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
                    content_type = CONTENT_TYPE_FILE
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
                if not uuid:
                    # This code block is a temporary hack until every hugo2ocw output file has a uuid
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


def import_ocw2hugo_course(bucket_name, prefix, key):
    """
    Extract OCW course content for a course

    Args:
        bucket (s3.Bucket): An s3 bucket
        prefix (str): S3 prefix before start of course_id path
        key (str): The S3 prefix for the course homepage.
    """
    s3 = get_s3_resource()
    bucket = s3.Bucket(bucket_name)
    url_path = os.path.splitext(os.path.basename(key))[0]
    s3_content = json.loads(get_s3_object_and_read(bucket.Object(key)).decode())
    website, _ = Website.objects.update_or_create(
        url_path=url_path,
        defaults={
            "title": s3_content.get("course_title", None),
            "publish_date": s3_content.get("publishdate", None),
            "metadata": s3_content,
        },
    )
    import_ocw2hugo_content(bucket, prefix, website)
