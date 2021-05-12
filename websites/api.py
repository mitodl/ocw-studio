"""API functionality for websites"""
import re
from typing import Optional

from websites.models import WebsiteContent


def get_valid_new_filename(
    website_pk: str, content_type: str, dirpath: Optional[str], filename_base: str
) -> str:
    """
    Given a filename to act as a base/prefix, returns a filename that will satisfy unique constraints,
    adding/incrementing a numerical suffix as necessary.

    Examples:
        In database: WebsiteContent(filename="my-filename")...
            get_valid_new_filename("my-filename") == "my-filename-2"
        In database: WebsiteContent(filename="my-filename-99")...
            get_valid_new_filename("my-filename-99") == "my-filename-100"
    """
    existing_filename = (
        WebsiteContent.objects.all_with_deleted()
        .filter(
            website_id=website_pk,
            type=content_type,
            dirpath=dirpath,
            filename__startswith=filename_base,
        )
        .order_by("-filename")
        .values_list("filename", flat=True)
        .first()
    )
    if existing_filename is None:
        return filename_base
    filename_match = re.match(r"({})-?(\d+)?".format(filename_base), existing_filename)
    suffix = int(filename_match.groups()[1] or 1) + 1
    return f"{filename_base}-{suffix}"
