"""Websites utils"""

import logging
import re
from typing import Any

from django.conf import settings
from django.db.models import Q

from websites import constants

log = logging.getLogger(__name__)

UUID_REGEX_STR = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

# Compiled regexes for parse_resource_uuid (moved to module scope for performance)
_RESOURCE_LINK_AND_EMBED_REGEX = re.compile(
    rf"""
    \{{\{{%\s+resource_link\s+"?({UUID_REGEX_STR})"?\s+"(.+?)"\s+%\}}\}}
    |
    \{{\{{<\s+resource\s+([^>]*)>\}}\}}
    """,
    re.VERBOSE,
)
_ATTRIBUTE_UUID_REGEX = re.compile(
    rf'(?:^|\s)(?:uuid|href_uuid|href-uuid)\s*=\s*"?({UUID_REGEX_STR})"?(?=\s|$)'
)
_POSITIONAL_UUID_REGEX = re.compile(rf'^\s*"?({UUID_REGEX_STR})"?(?=\s|$)')


def permissions_group_name_for_role(role, website):
    """Get the website group name for a given role"""
    if role == constants.ROLE_GLOBAL:
        return constants.GLOBAL_ADMIN
    elif role in constants.ROLE_GROUP_MAPPING:
        return f"{constants.ROLE_GROUP_MAPPING[role]}{website.uuid.hex}"
    else:
        msg = f"Invalid role for a website group: {role}"
        raise ValueError(msg)


def get_dict_field(obj: dict, field_path: str) -> Any:
    """Return the value of a potentially nested dict path"""
    fields = field_path.split(".")
    current_obj = obj
    for field in fields[:-1]:
        current_obj = current_obj.get(field, {})
    return current_obj.get(fields[-1])


def set_dict_field(obj: dict, field_path: str, value: Any):
    """Set the value of a potentially nested dict path"""
    fields = field_path.split(".")
    current_obj = obj
    for field in fields[:-1]:
        current_obj_field = current_obj.get(field)
        if current_obj_field:
            current_obj = current_obj_field
        else:
            current_obj[field] = {}
            current_obj = current_obj[field]
    current_obj[fields[-1]] = value


def get_dict_query_field(dict_field_name: str, sub_field: str):
    """Generate django query key for searching a nested json feild"""
    return dict_field_name + "__" + sub_field.replace(".", "__")


def get_valid_base_filename(filename: str, content_type: str) -> str:
    """Avoid forbidden filenames that could confuse hugo"""
    if filename in constants.CONTENT_FILENAMES_FORBIDDEN:
        return f"{filename}-{content_type}"
    return filename


def resource_reference_field_filter(
    field: dict,
    resource_id: str,
    website: "Website",  # noqa: F821
) -> Q | None:
    """
    Generates an appropriate Q expression to filter a field for a resource usage.
    """  # noqa: D401
    q = None

    if field.get("widget") == "markdown" and (
        constants.CONTENT_TYPE_RESOURCE in field.get("link", [])
        or constants.CONTENT_TYPE_RESOURCE in field.get("embed", [])
    ):
        q = Q(markdown__icontains=resource_id)
    elif (
        field.get("widget") == "relation"
        and field.get("collection") == constants.CONTENT_TYPE_RESOURCE
    ):
        lookup_args = ["metadata", field["name"], "content"]

        if field.get("multiple", False):
            lookup_args.append("contains")

        lookup = "__".join(lookup_args)

        value = (
            resource_id
            if not field.get("cross_site", False)
            else [[resource_id, website.url_path]]
        )

        q = Q(**{lookup: value})
    elif field.get("widget") == "menu":
        lookup = "__".join(("metadata", field.get("name"), "contains"))
        q = Q(**{lookup: [{"identifier": resource_id}]})

    return q


def is_test_site(site_name: str) -> bool:
    """Return True if the provided site slug is configured as a test site."""
    return site_name in settings.OCW_TEST_SITE_SLUGS


def get_metadata_content_key(content) -> list:
    """Get the metadata content keys based on the content type."""
    content_type = content.type
    match content_type:
        case (
            constants.CONTENT_TYPE_RESOURCE_LIST
            | constants.CONTENT_TYPE_RESOURCE_COLLECTION
        ):
            content_keys = [
                constants.METADATA_FIELD_DESCRIPTION,
                constants.METADATA_FIELD_RESOURCES_CONTENT,
            ]
        case constants.CONTENT_TYPE_VIDEO_GALLERY:
            content_keys = [constants.METADATA_FIELD_VIDEO_GALLERY_VIDEOS]
        case constants.CONTENT_TYPE_METADATA:
            content_keys = [
                constants.METADATA_FIELD_COURSE_DESCRIPTION,
                constants.INSTRUCTORS_FIELD_CONTENT,
                constants.METADATA_FIELD_COURSE_IMAGE,
                constants.METADATA_FIELD_COURSE_IMAGE_THUMBNAIL,
            ]
        case constants.CONTENT_TYPE_RESOURCE:
            content_keys = [
                constants.METADATA_FIELD_IMAGE_CAPTION,
                constants.METADATA_FIELD_IMAGE_CREDIT,
            ]
        case constants.CONTENT_TYPE_COURSE_COLLECTION:
            content_keys = [
                constants.METADATA_FIELD_DESCRIPTION,
                constants.METADATA_FIELD_COVER_IMAGE,
                constants.METADATA_FIELD_COURSE_LISTS,
            ]
        case constants.CONTENT_TYPE_COURSE_LIST:
            content_keys = [
                constants.METADATA_FIELD_DESCRIPTION,
                constants.METADATA_FIELD_COURSE_LIST_COURSES,
            ]
        case (
            constants.CONTENT_TYPE_PROMO
            | constants.CONTENT_TYPE_TESTIMONIAL
            | constants.CONTENT_TYPE_STORY
        ):
            content_keys = [constants.METADATA_FIELD_IMAGE]
        case constants.CONTENT_TYPE_HOMEPAGE_SETTINGS:
            content_keys = [
                constants.METADATA_FIELD_FEATURED_PROMOS,
                constants.METADATA_FIELD_FEATURED_STORIES,
            ]
        case _:
            content_keys = []

    return content_keys


def parse_resource_uuid(text: str) -> list[str]:
    """
    Parse the input text to extract UUIDs from resource links.

    Args:
        text (str): The input text containing resource links.

    Returns:
        list[str]: A list of extracted UUIDs.
    """
    # This regex pattern matches two types of Hugo resource patterns:
    # 1. Hugo shortcode syntax: {{% resource_link "uuid" "title" %}} or
    #    {{% resource_link uuid "title" %}}
    # 2. Hugo resource/embed syntax: {{< resource ... >}}
    #
    # Pattern breakdown:
    # - Pattern 1: \{\{%\s+resource_link\s+"?([uuid])"?\s+"(.+?)"\s+%\}\}
    #   - \{\{%     : Matches literal "{{%"
    #   - \s+       : Matches one or more whitespace characters
    #   - resource_link : Matches literal "resource_link"
    #   - \s+       : Matches one or more whitespace characters
    #   - "?([uuid])"? : Captures UUID in group 1 with optional quotes
    #                    (full pattern below)
    #   - \s+       : Matches one or more whitespace characters
    #   - "(.+?)"   : Captures title text in group 2
    #   - \s+       : Matches one or more whitespace characters
    #   - %\}\}     : Matches literal "%}}"
    #
    # - Pattern 2: \{\{<\s+resource\s+([^>]*)>\}\}
    #   - \{\{<     : Matches literal "{{<"
    #   - \s+       : Matches one or more whitespace characters
    #   - resource  : Matches literal "resource"
    #   - \s+       : Matches one or more whitespace characters
    #   - ([^>]*)   : Captures all shortcode attributes in group 3
    #   - >\}\}     : Matches literal ">}}"
    #
    # UUID format: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}
    # Example: b02b216b-1e9e-4b5c-8b1b-9c275a834679
    matches = _RESOURCE_LINK_AND_EMBED_REGEX.findall(text)

    references = []
    for match in matches:
        if match[0]:
            references.append(match[0])
            continue

        if not match[2]:
            continue

        attr_references = _ATTRIBUTE_UUID_REGEX.findall(match[2])
        if attr_references:
            references.extend(attr_references)
            continue

        positional_match = _POSITIONAL_UUID_REGEX.match(match[2])
        if positional_match:
            references.append(positional_match.group(1))

    return references


def _extract_relation_text_ids(resource_data: list) -> list[str]:
    """Extract text_id values from relation widget data."""
    references = []
    for relation_value in resource_data:
        if isinstance(relation_value, str):
            references.append(relation_value)
        elif (
            isinstance(relation_value, list)
            and relation_value
            and isinstance(relation_value[0], str)
        ):
            # Cross-site relation widgets can store entries as
            # [text_id, website_name].
            references.append(relation_value[0])
        elif isinstance(relation_value, dict):
            # Handle both text_id (course-lists) and id (website-collections)
            relation_id = relation_value.get("text_id") or relation_value.get("id")
            if isinstance(relation_id, str):
                references.append(relation_id)
    return references


def compile_referencing_content(content) -> list[str]:
    """Compile referencing content for a website content instance."""
    references = []

    if content.type == constants.CONTENT_TYPE_NAVMENU:
        references = [
            item["identifier"]
            for item in content.metadata.get(constants.WEBSITE_CONTENT_LEFTNAV, [])
        ]
    else:
        if content.markdown:
            references += parse_resource_uuid(content.markdown)

        if content.metadata:
            content_keys = get_metadata_content_key(content)
            for content_key in content_keys:
                if resource_data := get_dict_field(content.metadata, content_key):
                    if isinstance(resource_data, list):
                        references.extend(_extract_relation_text_ids(resource_data))
                    elif isinstance(resource_data, str):
                        resource_data = resource_data.strip()
                        if re.fullmatch(UUID_REGEX_STR, resource_data):
                            references.append(resource_data)
                        else:
                            references.extend(parse_resource_uuid(resource_data))
                    else:
                        log.warning(
                            "Unexpected metadata type %s for key '%s' in content %s",
                            type(resource_data).__name__,
                            content_key,
                            content.text_id,
                        )
    return references
