""" API functionality for OCW course site import """
import json
import logging
import re
import uuid
from copy import deepcopy
from typing import Dict

import dateutil
import yaml
from django.conf import settings

from gdrive_sync.api import create_gdrive_folders, is_gdrive_enabled
from main.s3_utils import get_s3_object_and_read, get_s3_resource
from main.utils import get_dirpath_and_filename, is_valid_uuid
from ocw_import.constants import OCW_SECTION_TYPE_MAPPING, OCW_TYPE_ASSIGNMENTS
from websites.api import find_available_name, get_valid_new_filename
from websites.constants import (
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_TYPE_INSTRUCTOR,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    CONTENT_TYPE_VIDEO_GALLERY,
    EXTERNAL_IDENTIFIER_PREFIX,
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
            if key.endswith("course_legacy.json") and (
                not filter_str or filter_str in key
            ):
                yield key


def import_ocw2hugo_content(bucket, prefix, website):  # pylint:disable=too-many-locals
    """
    Import all content files for an ocw course from hugo2ocw output,
    and delete any obsolete content from prior imports

    Args:
        bucket (s3.Bucket): S3 bucket
        prefix (str): S3 prefix for filtering by course
        website (Website): Website to import content for
    """
    prior_content = website.websitecontent_set.exclude(
        type__in=[CONTENT_TYPE_NAVMENU, CONTENT_TYPE_METADATA, CONTENT_TYPE_INSTRUCTOR]
    ).values_list("text_id", flat=True)
    current_content = []
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
                content = convert_data_to_content(filepath, s3_content, website)
                if content:
                    current_content.append(content.text_id)
            except:  # pylint:disable=bare-except
                log.exception("Error saving WebsiteContent for %s", s3_key)
    obsolete_content = list(set(prior_content) - set(current_content))
    WebsiteContent.objects.filter(text_id__in=obsolete_content).delete()


def update_ocw2hugo_content(
    bucket, prefix, website, update_field
):  # pylint:disable=too-many-locals
    """
    update the update_field of all content files for an ocw course from hugo2ocw output

    Args:
        bucket (s3.Bucket): S3 bucket
        prefix (str): S3 prefix for filtering by course
        website (Website): Website to import content for
    """
    site_prefix = f"{prefix}{website.name}"

    is_metadata_field = False

    if update_field.startswith("metadata."):
        is_metadata_field = True
        update_field = update_field.replace("metadata.", "")

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
                text_id, content_data = get_content_data(filepath, s3_content, website)

                content_file = WebsiteContent.objects.filter(
                    website=website, text_id=text_id
                ).first()

                if content_file:
                    if is_metadata_field:
                        content_file.metadata[update_field] = content_data.get(
                            "metadata", {}
                        ).get(update_field, "")
                    else:
                        setattr(
                            content_file,
                            update_field,
                            content_data.get(update_field, ""),
                        )
                    content_file.save()

            except:  # pylint:disable=bare-except
                log.exception("Error saving WebsiteContent for %s", s3_key)


def get_learning_resource_types(content_json):
    """
    Get learning_resource_types for imported courses

    content_json(dict): json representation of other WebsiteContent data

    Returns:
    array[str]: the learning_resource_types for the content object
    """

    if "Section" in content_json.get("parent_type", ""):
        section_title = content_json.get("parent_title")
    elif "Section" in content_json.get("type", ""):
        section_title = content_json.get("title")
    else:
        return []

    if re.search(r"Assignment($|\s)", section_title):
        return [OCW_TYPE_ASSIGNMENTS]

    if OCW_SECTION_TYPE_MAPPING.get(section_title):
        return [OCW_SECTION_TYPE_MAPPING.get(section_title)]

    return []


def get_content_data(filepath, data, website):  # pylint:disable=too-many-locals
    """
    Get json data for WebsiteContent object from hugo data

    filepath(str): The path of the file (from S3 or git)
    data(str): The file data to be converted
    website (Website): The website to which the content belongs

    Returns:
    text_id (str): the uuid of the WebsiteContent objecet
    content_data (dict): json representation of the WebsiteContent contents
    """
    s3_content_parts = [
        part for part in re.split(re.compile(r"^---\n", re.MULTILINE), data) if part
    ]
    parent = None
    if len(s3_content_parts) >= 1:
        content_json = yaml.load(s3_content_parts[0], Loader=yaml.SafeLoader)
        text_id = str(uuid.UUID(content_json["uid"]))
        dirpath, filename_base = get_dirpath_and_filename(
            filepath, expect_file_extension=True
        )
        filename = get_valid_new_filename(website.pk, dirpath, filename_base, text_id)
        parent_uid = content_json.get("parent_uid", None)
        if dirpath == "content/resources":
            # This is a file
            content_type = CONTENT_TYPE_RESOURCE
        elif dirpath == "content/video_galleries":
            # This is a video gallery
            content_type = CONTENT_TYPE_VIDEO_GALLERY
        else:
            # This is a page
            content_type = CONTENT_TYPE_PAGE
        if parent_uid:
            parent, _ = WebsiteContent.objects.get_or_create(
                website=website, text_id=str(uuid.UUID(parent_uid))
            )
        file = content_json.get("file", None)

        content_json["learning_resource_types"] = get_learning_resource_types(
            content_json
        )

        if file:
            ocw_prefix = (
                website.starter.config.get("root-url-path", "courses")
                if website.starter
                else "courses"
            )
            file = re.sub(r"^/?coursemedia", ocw_prefix, file)

        content_data = {
            "is_page_content": True,
            "file": file,
            "metadata": content_json,
            "markdown": (s3_content_parts[1] if len(s3_content_parts) == 2 else None),
            "parent": parent,
            "title": content_json.get("title"),
            "type": content_type,
            "dirpath": dirpath,
            # Replace dots with dashes to simplify file name/extension parsing, and limit length
            "filename": filename.replace(".", "-")[0:CONTENT_FILENAME_MAX_LEN],
        }

        return text_id, content_data


def convert_data_to_content(filepath, data, website):
    """
    Convert file data into a WebsiteContent object

    Args:
        filepath(str): The path of the file (from S3 or git)
        data(str): The file data to be converted
        website (Website): The website to which the content belongs
    """
    text_id, base_defaults = get_content_data(filepath, data, website)

    content, _ = WebsiteContent.objects.update_or_create(
        website=website, text_id=text_id, defaults=base_defaults
    )
    return content


def get_short_id(name: str, metadata: Dict) -> str:
    """ Get a short_id from the metadata"""
    existing_site = Website.objects.filter(name=name).first()
    if existing_site and existing_site.short_id:
        return existing_site.short_id
    course_num = metadata.get("primary_course_number")
    if not course_num:
        raise ValueError("Primary course number is missing")
    short_id = (
        (
            "-".join(
                [
                    piece
                    for piece in [
                        re.sub(r"\(.+\)", "", course_num).strip(),
                        metadata.get("term", ""),
                        metadata.get("year", ""),
                    ]
                    if piece
                ]
            )
        )
        .lower()
        .replace(" ", "-")
    )
    short_id_exists = (
        Website.objects.exclude(name=name).filter(short_id=short_id).exists()
    )
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
        course_data (dict): Data from data/course_legacy.json
        website (Website): The course website
    """
    try:
        website_root = Website.objects.get(name=settings.ROOT_WEBSITE_NAME)
    except Website.DoesNotExist:
        log.error("No root web site found, name=%s", settings.ROOT_WEBSITE_NAME)
        return

    metadata = {}
    metadata["course_title"] = course_data["course_title"]
    metadata["course_description"] = course_data["course_description"]
    metadata["primary_course_number"] = course_data["primary_course_number"]
    metadata["extra_course_numbers"] = ",".join(course_data["extra_course_numbers"])
    metadata["course_image"] = course_data["course_image"]
    metadata["course_image_thumbnail"] = course_data["course_image_thumbnail"]
    metadata["legacy_uid"] = course_data["legacy_uid"]

    with open("static/js/resources/departments.json", "r") as departments_json_file:
        departments_json = json.load(departments_json_file)
        metadata["department_numbers"] = list(
            map(
                (
                    lambda course_department: next(
                        (
                            department["depNo"]
                            for department in departments_json
                            if department["title"] == course_department["department"]
                        ),
                        None,
                    )
                ),
                course_data["departments"],
            )
        )
    # level used to be a { level, url } dictionary, but now it's a [level] for any number of levels
    # handle both cases temporarily for back compat
    metadata["level"] = (
        [course_data["level"]["level"]]
        if isinstance(course_data["level"], dict)
        else course_data["level"]
    )
    metadata["learning_resource_types"] = list(
        map(
            lambda course_feature: course_feature["feature"],
            course_data["course_features"],
        )
    )
    metadata["topics"] = course_data["topics"]

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

    metadata[INSTRUCTORS_FIELD_NAME] = {
        "website": website_root.name,
        "content": [content.text_id for content in instructor_contents],
    }

    metadata["term"] = course_data["term"]
    metadata["year"] = course_data.get("year")

    WebsiteContent.objects.update_or_create(
        type=CONTENT_TYPE_METADATA,
        website=website,
        defaults={
            "text_id": CONTENT_TYPE_METADATA,
            "title": "Course Metadata",
            "metadata": metadata,
        },
    )


def import_ocw2hugo_menu(menu_data, website):
    """
    Create and populate a navmenu for the course

    Args:
        menu_data (dict): Data from config/_default/menus.yaml
        website (Website): The course website
    """
    menu_data = deepcopy(menu_data)
    for item in menu_data["leftnav"]:
        if "identifier" not in item:
            item["identifier"] = f"{EXTERNAL_IDENTIFIER_PREFIX}{uuid.uuid4().hex}"

        for key in ["identifier", "parent"]:
            if is_valid_uuid(item.get(key, "")):
                item[key] = str(uuid.UUID(item[key]))

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
    name = path.replace("/data/course_legacy.json", "", 1)
    menu_data = yaml.load(
        get_s3_object_and_read(
            bucket.Object(f"{prefix}{name}/config/_default/menus.yaml")
        ),
        Loader=yaml.FullLoader,
    )
    if name in NON_ID_COURSE_NAMES:
        return
    try:
        first_published_to_production = parse_date(course_data.get("publishdate", None))
    except (ValueError, TypeError):
        first_published_to_production = None
        course_data["publishdate"] = None
    try:
        website, _ = Website.objects.update_or_create(
            name=name,
            defaults={
                "title": course_data.get("course_title", f"Course Site ({name})"),
                "first_published_to_production": first_published_to_production,
                "metadata": course_data,
                "short_id": get_short_id(name, course_data),
                "starter_id": starter_id,
                "source": WEBSITE_SOURCE_OCW_IMPORT,
            },
        )
        import_ocw2hugo_sitemetadata(course_data, website)
        import_ocw2hugo_menu(menu_data, website)
        import_ocw2hugo_content(bucket, prefix, website)
        if is_gdrive_enabled() and website.gdrive_folder is None:
            create_gdrive_folders(website.short_id)
    except:  # pylint:disable=bare-except
        log.exception("Error saving website %s", path)


def update_ocw2hugo_course(bucket_name, prefix, path, content_update_field):
    """
    Extract OCW course content for a course

    Args:
        bucket_name (str): An s3 bucket name
        prefix (str): S3 prefix before start of course_id path
        path (str): The course URL path
        content_update_field (string): Website content field that should be overwritten
    """
    s3 = get_s3_resource()
    bucket = s3.Bucket(bucket_name)
    name = path.replace("/data/course_legacy.json", "", 1)

    website = Website.objects.filter(name=name).first()

    if website:
        update_ocw2hugo_content(bucket, prefix, website, content_update_field)
