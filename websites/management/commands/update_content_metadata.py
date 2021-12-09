""" Update content metadata for websites based on a specific starter """
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from websites.site_config_api import SiteConfig
from websites.models import WebsiteContent, WebsiteStarter


class Command(BaseCommand):
    """ Update content metadata for websites based on a specific starter """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "starter",
            help="The WebsiteStarter slug to process",
        )
        parser.add_argument(
            "-t",
            "--type",
            dest="type",
            default="resource",
            help="Only update metadata of this_type (default = resource)",
        )
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only update metadata for websites with names/short_ids matching this filter",
        )
        parser.add_argument(
            "-s",
            "--source",
            dest="source",
            default="studio",
            help=f"Only update metadata for websites that are based on this source (default=studio)",
        )

    def handle(self, *args, **options):

        filter_str = options["filter"].lower()
        starter_str = options["starter"]
        source_str = options["source"]
        type_str = options["type"]

        content_qset = WebsiteContent.objects.filter(
            website__starter__slug=starter_str, type=type_str
        )
        if filter_str:
            content_qset = content_qset.filter(
                Q(website__name__startswith=filter_str)
                | Q(website__short_id__startswith=filter_str)
            )
        if source_str:
            content_qset = content_qset.filter(website__source=source_str)

        self.stdout.write(
            f"Update {type_str} metadata for websites based on starter {starter_str}, source={source_str}"
        )

        base_metadata = SiteConfig(
            WebsiteStarter.objects.get(slug=starter_str).config
        ).generate_item_metadata(type_str, cls=WebsiteContent)
        with transaction.atomic():
            for content in content_qset.iterator():
                if set(base_metadata.keys()).symmetric_difference(
                    set(content.metadata.keys())
                ):
                    content.metadata = {**base_metadata, **content.metadata}
                    content.save()

        self.stdout.write(
            f"Done Updating {type_str} metadata for websites based on starter {starter_str}, source {source_str}"
        )
