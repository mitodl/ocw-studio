"""Websites utils"""

import re
from typing import Any, Optional

from django.conf import settings
from django.db.models import Q

from websites import constants


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
) -> Optional[Q]:
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
    return site_name in settings.OCW_TEST_SITE_SLUGS


def get_metadata_content_key(content) -> list:
    content_type = content.type
    match content_type:
        case (
            constants.CONTENT_TYPE_RESOURCE_LIST,
            constants.CONTENT_TYPE_RESOURCE_COLLECTION,
        ):
            content_keys = ["description"]
        case constants.CONTENT_TYPE_METADATA:
            content_keys = ["course_description"]
        case _:
            content_keys = []

    return content_keys


def parse_string(text: str) -> str:
    """
    Parse the input text to extract UUIDs from resource links.

    Args:
        text (str): The input text containing resource links.

    Returns:
        str: A list of extracted UUIDs.
    """
    pattern = r"""
    \{\{%\s+resource_link\s+"([a-f0-9-]{36})"\s+"([^"]+)"\s+%\}\}
    |
    \{\{<\s+resource\s+uuid="([a-f0-9-]{36})"\+s>\}\}
    """

    regex = re.compile(pattern, re.VERBOSE)
    matches = regex.findall(text)

    # Extract UUIDs by checking which group captured the value
    return [
        _match[0]
        or _match[2]  # match[0] for first group UUID, match[2] for second group UUID
        for _match in matches
    ]
