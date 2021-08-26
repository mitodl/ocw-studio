""" API functionality for OCW course site import """
import json
import logging
import re
import uuid

import dateutil
import yaml
from django.conf import settings

from main.s3_utils import get_s3_object_and_read, get_s3_resource
from main.utils import get_dirpath_and_filename
from websites.api import find_available_name
from websites.constants import (
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_TYPE_INSTRUCTOR,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    COURSE_PAGE_LAYOUTS,
    COURSE_RESOURCE_LAYOUTS,
    INSTRUCTORS_FIELD_NAME,
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


def parse_date(date_string):
    """
    Small utility function for calling dateutil.parser.parse, done so we can
    mock out date parsing in unit tests

    Args:
        date_string (str): A date string to parse
    Returns:
        A datetime.datetime object
    """
    return dateutil.parser.parse(date_string)


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
    site_prefix = f"{prefix}{website.name}"
    for resp in bucket.meta.client.get_paginator("list_objects").paginate(
        Bucket=bucket.name, Prefix=f"{site_prefix}/content"
    ):
        for obj in resp["Contents"]:
            s3_key = obj["Key"]
            s3_content = get_s3_object_and_read(bucket.Object(s3_key)).decode()
            if obj["Key"].startswith(site_prefix):
                filepath = obj["Key"].replace(site_prefix, "", 1)
            else:
                filepath = obj["Key"]
            try:
                convert_data_to_content(filepath, s3_content, website)
            except:  # pylint:disable=bare-except
                log.exception("Error saving WebsiteContent for %s", s3_key)


def convert_data_to_content(filepath, data, website):  # pylint:disable=too-many-locals
    """
    Convert file data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website: The website to which the content belongs
    """
    s3_content_parts = [
        part for part in re.split(re.compile(r"^---\n", re.MULTILINE), data) if part
    ]
    parent = None
    if len(s3_content_parts) >= 1:
        content_json = yaml.load(s3_content_parts[0], Loader=yaml.SafeLoader)
        layout = content_json.get("layout", None)
        uid = content_json.get("uid", None)
        dirpath, filename = get_dirpath_and_filename(
            filepath, expect_file_extension=True
        )
        parent_uid = content_json.get("parent_uid", None)
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
            "is_page_content": True,
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


def get_short_id(metadata):
    """ Get a short_id from the metadata"""
    course_num = metadata.get("primary_course_number")
    if not course_num:
        raise ValueError("Primary course number is missing")
    term = "-".join(metadata.get("term", "").split())
    short_id = "-".join(segment for segment in [course_num, term] if segment).lower()
    short_id_exists = Website.objects.filter(short_id=short_id).exists()
    if short_id_exists:
        short_id_prefix = f"{short_id}-"
        short_id = find_available_name(
            Website.objects.filter(short_id__startswith=short_id),
            short_id_prefix,
            "short_id",
            max_length=100,
        )
    return short_id


def import_ocw2hugo_sitemetadata(
    course_data, website
):  # pylint:disable=too-many-locals
    """
    Create and populate sitemetadata from an ocw course

    Args:
        course_data (dict): Data from data/course.json
        website (Website): The course website
    """
    try:
        website_root = Website.objects.get(name=settings.ROOT_WEBSITE_NAME)
    except Website.DoesNotExist:
        log.error("No root web site found, name=%s", settings.ROOT_WEBSITE_NAME)
        return

    instructor_contents = []
    for instructor in course_data["instructors"]:
        uid = instructor["uid"]
        text_id = str(uuid.UUID(uid))
        first_name = instructor.get("first_name", "")
        last_name = instructor.get("last_name", "")
        middle_initial = instructor.get("middle_initial", "")
        salutation = instructor.get("salutation", "")
        middle_initial_plus_space = f"{middle_initial} " if middle_initial else ""
        salutation_plus_space = f"{salutation} " if salutation else ""

        instructor_content, _ = WebsiteContent.objects.update_or_create(
            website=website_root,
            text_id=text_id,
            defaults={
                "metadata": {
                    "headless": True,
                    "first_name": first_name,
                    "last_name": last_name,
                    "middle_initial": middle_initial,
                    "salutation": salutation,
                },
                "title": f"{salutation_plus_space}{first_name} {middle_initial_plus_space}{last_name}",
                "type": CONTENT_TYPE_INSTRUCTOR,
                "dirpath": "content/instructors",
                "filename": text_id,
                "is_page_content": True,
            },
        )
        instructor_contents.append(instructor_content)

    WebsiteContent.objects.update_or_create(
        type=CONTENT_TYPE_METADATA,
        website=website,
        defaults={
            "text_id": CONTENT_TYPE_METADATA,
            "title": "Course Metadata",
            "metadata": {
                INSTRUCTORS_FIELD_NAME: {
                    "website": website_root.name,
                    "content": [content.text_id for content in instructor_contents],
                }
            },
        },
    )


def import_ocw2hugo_menu(menu_data, website):
    """
    Create and populate a navmenu for the course

    Args:
        menu_data (dict): Data from config/_default/menus.yaml
        website (Website): The course website
    """
    for i in range(len(menu_data["leftnav"])):
        if "identifier" in menu_data["leftnav"][i]:
            menu_data["leftnav"][i]["identifier"] = str(
                uuid.UUID(menu_data["leftnav"][i]["identifier"])
            )
        if "parent" in menu_data["leftnav"][i]:
            menu_data["leftnav"][i]["parent"] = str(
                uuid.UUID(menu_data["leftnav"][i]["parent"])
            )
    WebsiteContent.objects.update_or_create(
        filename="menus.yaml",
        website=website,
        defaults={
            "title": "Left Nav",
            "type": CONTENT_TYPE_NAVMENU,
            "text_id": CONTENT_TYPE_NAVMENU,
            "dirpath": "config/_default/menus.yaml",
            "metadata": menu_data,
        },
    )


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
    course_data = json.loads(get_s3_object_and_read(bucket.Object(path)).decode())
    name = course_data.get("course_id")
    menu_data = yaml.load(
        get_s3_object_and_read(
            bucket.Object(f"{prefix}{name}/config/_default/menus.yaml")
        ),
        Loader=yaml.FullLoader,
    )
    if name in NON_ID_COURSE_NAMES:
        return
    try:
        publish_date = parse_date(course_data.get("publishdate", None))
    except ValueError:
        publish_date = None
        course_data["publishdate"] = None
    try:
        website, _ = Website.objects.update_or_create(
            name=name,
            defaults={
                "title": course_data.get("course_title", f"Course Site ({name})"),
                "publish_date": publish_date,
                "metadata": course_data,
                "short_id": get_short_id(course_data),
                "starter_id": starter_id,
                "source": WEBSITE_SOURCE_OCW_IMPORT,
            },
        )
        import_ocw2hugo_sitemetadata(course_data, website)
        import_ocw2hugo_menu(menu_data, website)
        import_ocw2hugo_content(bucket, prefix, website)
    except:  # pylint:disable=bare-except
        log.exception("Error saving website %s", path)


def generate_topics_dict(course_paths, bucket_name):
    """
    Crawl through a S3 bucket with course data output from ocw-to-hugo and construct a list of topics

    Args:
        course_paths (list of str): List of paths to the data/course.json file for each course
        bucket_name (str): The name of the S3 bucket to use

    Returns:
        dict:
            Nested dicts and lists representing topics, subtopics, and specialties
    """
    topics = {}

    s3 = get_s3_resource()
    bucket = s3.Bucket(bucket_name)
    for path in course_paths:
        course_data = json.loads(get_s3_object_and_read(bucket.Object(path)).decode())

        for topic_obj in course_data.get("topics", []):
            topic = topic_obj["topic"]
            if topic not in topics:
                topics[topic] = {}

            for subtopic_obj in topic_obj["subtopics"]:
                subtopic = subtopic_obj["subtopic"]
                if subtopic not in topics[topic]:
                    topics[topic][subtopic] = set()
                for speciality in subtopic_obj["specialities"]:
                    topics[topic][subtopic].add(speciality["speciality"])

    for topic, subtopic_dict in topics.items():
        for subtopic in subtopic_dict.keys():
            subtopic_dict[subtopic] = sorted(subtopic_dict[subtopic])

    return topics


def delete_unpublished_courses(paths=None, filter_str=None):
    """
    Remove all unpublished courses based on paths that don't exist anymore

    Args:
        paths (list of str): list of paths to course data templates
        filter_str (str): (Optional) If specified, filter courses to remove
    """
    if not paths:
        return
    course_ids = list(map((lambda key: key.replace("/data/course.json", "", 1)), paths))
    unpublished_courses = Website.objects.filter(
        source=WEBSITE_SOURCE_OCW_IMPORT
    ).exclude(metadata__course_id__in=course_ids)
    if filter_str:
        unpublished_courses = unpublished_courses.filter(
            metadata__course_id__contains=filter_str
        )
    unpublished_courses.delete()
