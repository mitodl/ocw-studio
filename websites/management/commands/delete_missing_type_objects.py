from django.core.management import BaseCommand  # noqa: INP001
from safedelete.models import HARD_DELETE

from websites.models import WebsiteContent


class Command(BaseCommand):
    """Delete objects in the Django database that are missing a type"""

    help = __doc__

    def handle(self, *args, **options):  # noqa: ARG002
        missing_type_content = WebsiteContent.objects.all(force_visibility=True).filter(
            type=""
        )
        for content in missing_type_content:
            content.delete(force_policy=HARD_DELETE)
        self.stdout.write(
            str(len(missing_type_content)) + " objects with missing type deleted.\n"
        )
