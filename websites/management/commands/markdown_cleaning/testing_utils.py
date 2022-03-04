from unittest.mock import patch
from contextlib import contextmanager

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

