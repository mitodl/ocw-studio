"""Updates derived values in WebsiteContent records to match the site config"""  # noqa: E501, INP001
import sys

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.site_config_api import SiteConfig


class Command(WebsiteFilterCommand):
    """Updates derived values in WebsiteContent records to match the site config"""

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-s",
            "--starter-slug",
            dest="starter_slug",
            default="",
            help="If specified, only sync contents for websites that user the given starter.",  # noqa: E501
        )

    def handle(self, *args, **options):  # pylint:disable=too-many-locals  # noqa: C901
        super().handle(*args, **options)
        starter_qset = WebsiteStarter.objects.all()
        starter_slug = options.get("starter_slug")
        if starter_slug:
            starter_qset = starter_qset.filter(slug=starter_slug)
            if not starter_qset.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"WebsiteStarter with slug '{starter_slug}' not found."
                    )
                )
                sys.exit(1)

        updates_performed = False
        for starter in starter_qset:
            sites_updated = 0
            contents_updated = 0
            page_content_config_item_names = []
            other_config_item_names = []
            site_config = SiteConfig(starter.config)
            for config_item in site_config.iter_items():
                if not config_item.has_file_target():
                    continue
                if site_config.is_page_content(config_item):
                    page_content_config_item_names.append(config_item.name)
                else:
                    other_config_item_names.append(config_item.name)
            websites = self.filter_websites(
                websites=Website.objects.filter(starter=starter)
            )
            for website in websites:
                _contents_updated = WebsiteContent.objects.filter(
                    website=website,
                    type__in=page_content_config_item_names,
                    is_page_content=False,
                ).update(is_page_content=True)
                _contents_updated += WebsiteContent.objects.filter(
                    website=website,
                    type__in=other_config_item_names,
                    is_page_content=True,
                ).update(is_page_content=False)
                if _contents_updated:
                    contents_updated += _contents_updated
                    sites_updated += 1

            if contents_updated:
                updates_performed = True
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Starter '{starter.name}':\n"
                        f"  Updated {sites_updated} Website(s), {contents_updated} WebsiteContent(s)"  # noqa: E501
                    )
                )

        if not updates_performed:
            self.stdout.write(
                self.style.WARNING("Data already synced. No updates performed.")
            )
