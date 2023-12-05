"""Export the courses denoted in settings.OCW_WWW_TEST_SLUG and settings.OCW_COURSE_TEST_SLUG"""  # noqa: E501, INP001
import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management import BaseCommand

from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """Export the courses denoted in settings.OCW_WWW_TEST_SLUG and settings.OCW_COURSE_TEST_SLUG"""  # noqa: E501

    help = __doc__  # noqa: A003

    def handle(self, *args, **options):  # noqa: ARG002
        www_slug = settings.OCW_WWW_TEST_SLUG
        course_slug = settings.OCW_COURSE_TEST_SLUG
        websites = Website.objects.filter(name__in=[www_slug, course_slug])
        content = WebsiteContent.objects.filter(website__in=websites)
        websites_data = json.dumps(
            json.loads(serializers.serialize("json", websites)), indent=2
        )
        content_data = json.dumps(
            json.loads(serializers.serialize("json", content)), indent=2
        )
        with Path("test_site_fixtures/test_websites.json").open(
            mode="w", encoding="utf-8"
        ) as test_websites_file:
            test_websites_file.write(websites_data)
        with Path("test_site_fixtures/test_website_content.json").open(
            mode="w", encoding="utf-8"
        ) as test_website_content_file:
            test_website_content_file.write(content_data)
        self.stdout.write("Test site content exported")
