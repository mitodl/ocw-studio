from django.core.management import BaseCommand
from safedelete.models import HARD_DELETE

from websites.models import WebsiteContent


class Command(BaseCommand):
    """Delete objects in the Django database that are missing a type"""

    help = __doc__

    def handle(self, *args, **options):
        for content in WebsiteContent.objects.all(force_visibility=True).filter(
            type=""
        ):
            content.delete(force_policy=HARD_DELETE)
