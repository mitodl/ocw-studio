""" API functionality for OCW course site import """
import json
import logging
import pathlib
import re
import uuid

import toml
import yaml
from dateutil import parser as dateparser

from main.s3_utils import get_s3_object_and_read, get_s3_resource
from main.utils import get_dirpath_and_filename
from websites.constants import (
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    COURSE_HOME,
    COURSE_PAGE_LAYOUTS,
    COURSE_RESOURCE_LAYOUTS,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.models import Website, WebsiteContent


log = logging.getLogger(__name__)

NON_ID_COURSE_NAMES = [
    "biology",
    "chemistry",
    "engineering",
    "humanities-and-social-sciences",
    "iit-jee",
    "mathematics",
    "more",
    "physics",
]


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
    for resp in paginator.paginate(Bucket=bucket.name, Prefix=f"{prefix}"):
        for obj in resp["Contents"]:
            key = obj["Key"]
            if key.endswith("course.json") and (not filter_str or filter_str in key):
                yield key


def import_ocw2hugo_content(bucket, prefix, website):  # pylint:disable=too-many-locals
    """
    Import all content files for an ocw course from hugo2ocw output

    Args:
        bucket (s3.Bucket): S3 bucket
        prefix (str): S3 prefix for filtering by course
        website (Website): Website to import content for
    """
    course_home_s3_content = get_s3_object_and_read(
        bucket.Object(f"{prefix}{website.name}/content/_index.md")
    ).decode()
    course_home_s3_content_parts = [
        part
        for part in re.split(
            re.compile(r"^---\n", re.MULTILINE), course_home_s3_content
        )
        if part
    ]
    course_home_uuid = yaml.load(
        course_home_s3_content_parts[0], Loader=yaml.Loader
    ).get("uid", COURSE_HOME)
    for resp in bucket.meta.client.get_paginator("list_objects").paginate(
        Bucket=bucket.name, Prefix=f"{prefix}{website.name}"
    ):
        for obj in resp["Contents"]:
            s3_key = obj["Key"]
            s3_content = get_s3_object_and_read(bucket.Object(s3_key)).decode()
            filepath = obj["Key"].replace(prefix, "")
            try:
                convert_data_to_content(filepath, s3_content, website, course_home_uuid)
            except:  # pylint:disable=bare-except
                log.exception("Error saving WebsiteContent for %s", s3_key)


def convert_data_to_content(filepath, data, website, course_home_uuid):
    """
    Convert file data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website: The website to which the content belongs
        course_home_uuid: The UUID of the course page
    """
    file_extension = pathlib.Path(filepath).suffix
    if file_extension in CONVERSION_FUNCTIONS.keys():
        return CONVERSION_FUNCTIONS[file_extension](
            filepath=filepath,
            data=data,
            website=website,
            course_home_uuid=course_home_uuid,
        )
    else:
        log.exception("Unsupported extension: %s", filepath)
    return None


# pylint:disable=unused-argument
def convert_md_to_content(
    filepath="", data="", website=None, course_home_uuid=None, **kwargs
):  # pylint:disable=too-many-locals
    """
    Convert markdown data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website: The website to which the content belongs
        course_home_uuid: The UUID of the course page
    """
    s3_content_parts = [
        part for part in re.split(re.compile(r"^---\n", re.MULTILINE), data) if part
    ]
    parent = None
    if len(s3_content_parts) >= 1:
        content_json = yaml.load(s3_content_parts[0], Loader=yaml.Loader)
        layout = content_json.get("layout", None)
        menu = content_json.get("menu", None)
        uid = content_json.get("uid", None)
        dirpath, filename = get_dirpath_and_filename(
            filepath, expect_file_extension=True
        )
        if menu:
            menu_values = list(menu.values())[0]
            parent_uid = menu_values.get("parent", course_home_uuid)
        else:
            parent_uid = content_json.get("parent", None)
        if layout in COURSE_PAGE_LAYOUTS:
            # This is a page
            content_type = CONTENT_TYPE_PAGE
        elif layout in COURSE_RESOURCE_LAYOUTS:
            # This is a file
            content_type = CONTENT_TYPE_RESOURCE
        if parent_uid:
            parent, _ = WebsiteContent.objects.get_or_create(
                website=website, text_id=str(uuid.UUID(parent_uid))
            )
        base_defaults = {
            "metadata": content_json,
            "markdown": (s3_content_parts[1] if len(s3_content_parts) == 2 else None),
            "parent": parent,
            "title": content_json.get("title"),
            "type": content_type,
            "dirpath": dirpath,
            # Replace dots with dashes to simplify file name/extension parsing, and limit length
            "filename": filename.replace(".", "-")[0:CONTENT_FILENAME_MAX_LEN],
        }
        if not uid:
            log.error("No UUID (text ID): %s", filepath)
        else:
            content, _ = WebsiteContent.objects.update_or_create(
                website=website, text_id=str(uuid.UUID(uid)), defaults=base_defaults
            )
            return content


# pylint:disable=unused-argument
def convert_json_to_resource(filepath="", data="", website=None, **kwargs):
    """
    Convert json data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website: The website to which the content belongs
    """
    return save_resource(
        filepath=filepath, extension="json", data=json.loads(data), website=website
    )


# pylint:disable=unused-argument
def convert_toml_to_resource(filepath="", data="", website=None, **kwargs):
    """
    Convert toml data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website: The website to which the content belongs
    """
    return save_resource(
        filepath=filepath,
        extension="toml",
        data=toml.loads(data),
        website=website,
    )


def save_resource(filepath, extension="", data="", website=None):
    """
    Save a WebsiteContent object of type CONTENT_TYPE_RESOURCE

    Args:
        filepath(str): The path of the file (from S3 or git)
        extension(str): The file extension of the file to be saved
        data(str): The file data to be converted
        website: The website to which the content belongs
    """
    uid = uuid.uuid4()
    dirpath, filename = get_dirpath_and_filename(filepath, expect_file_extension=True)
    base_defaults = {
        "metadata": data,
        "markdown": "",
        "parent": None,
        "title": f"{filename}.{extension}",
        "type": CONTENT_TYPE_RESOURCE,
    }
    content, _ = WebsiteContent.objects.update_or_create(
        website=website,
        dirpath=dirpath,
        filename=filename,
        defaults={**base_defaults, "text_id": str(uid)},
    )
    return content


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
    s3_content = json.loads(get_s3_object_and_read(bucket.Object(path)).decode())
    name = s3_content.get("course_id")
    if name in NON_ID_COURSE_NAMES:
        return
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


CONVERSION_FUNCTIONS = {
    ".md": convert_md_to_content,
    ".json": convert_json_to_resource,
    ".toml": convert_toml_to_resource,
}
