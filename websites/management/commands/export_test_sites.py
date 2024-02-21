"""Export the courses denoted in settings.OCW_TEST_SITE_SLUGS"""  # noqa: INP001
import json
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder

from websites.models import Website, WebsiteContent
from websites.serializers import ExportWebsiteContentSerializer, ExportWebsiteSerializer


class Command(BaseCommand):
    """Export the courses denoted in settings.OCW_TEST_SITE_SLUGS"""

    help = __doc__  # noqa: A003

    def handle(self, *args, **options):  # noqa: ARG002
        websites = Website.objects.filter(
            name__in=settings.OCW_TEST_SITES_SLUGS
        ).order_by("pk")
        serialized_websites = ExportWebsiteSerializer(instance=websites, many=True).data
        content = WebsiteContent.objects.filter(website__in=websites).order_by("pk")
        serialized_website_content = ExportWebsiteContentSerializer(
            instance=content, many=True
        ).data
        websites_data = json.dumps(serialized_websites, indent=2, cls=DjangoJSONEncoder)
        content_data = json.dumps(
            serialized_website_content, indent=2, cls=DjangoJSONEncoder
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
