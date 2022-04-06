from contextlib import contextmanager
from unittest.mock import patch

from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag


@contextmanager
def patch_website_contents_all(website_contents):
    with patch("websites.models.WebsiteContent.all_objects.all") as mock:
        mock.return_value.prefetch_related.return_value = website_contents
        yield mock


@contextmanager
def patch_website_all(websites):
    with patch("websites.models.Website.objects.all") as mock:
        mock.return_value = websites
        yield mock


@contextmanager
def allow_invalid_uuids():
    with patch("main.utils.is_valid_uuid"):
        yield
