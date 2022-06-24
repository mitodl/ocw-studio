""" Update content metadata for websites based on a specific starter """
from django.db import transaction

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import WebsiteContent, WebsiteStarter
from websites.site_config_api import SiteConfig
from websites.utils import get_dict_field, set_dict_field


class Command(WebsiteFilterCommand):
    """Update content metadata to the default value spcecified in starter. Only
    affects content whose value for that metadata entry are null or empty.
    """

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--starter", help="The WebsiteStarter slug to process", required=True
        )
        parser.add_argument(
            "--field",
            help="The metadata field's name path to update, in dot notation. Example: image_metadata.caption",
            required=True,
        )
        parser.add_argument(
            "-t",
            "--type",
            dest="type",
            help="Only update metadata for content with this type.",
            required=True,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        starter_str = options["starter"]
        field_path = options["field"]
        type_str = options["type"]

        content_qset = WebsiteContent.objects.filter(
            website__starter__slug=starter_str, type=type_str
        )
        content_qset = self.filter_website_contents(content_qset)

        base_metadata = SiteConfig(
            WebsiteStarter.objects.get(slug=starter_str).config
        ).generate_item_metadata(type_str, cls=WebsiteContent, use_defaults=True)
        default_value = get_dict_field(base_metadata, field_path)
        if default_value is None:
            raise Exception(f"Metadata field {field_path} has no default")

        def should_update(website_content):
            current_value = get_dict_field(website_content.metadata, field_path)
            return current_value is None or current_value == ""

        expected_updated = sum(1 for wc in content_qset.iterator() if should_update(wc))

        confirmation = input(
            f"""You are about to change {expected_updated} records metadata value:
    field:     {field_path}
    new value: {default_value}
    old value: '' or null

Would you like to proceed? (y/n):"""
        )
        if confirmation != "y":
            self.stdout.write("Aborting...")
            return

        updated = 0
        with transaction.atomic():
            for content in content_qset.iterator():
                if should_update(content):
                    set_dict_field(content.metadata, field_path, default_value)
                    content.save()
                    updated += 1

        self.stdout.write(f"Finished updating {updated} records.")
