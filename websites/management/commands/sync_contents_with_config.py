"""Updates derived values in WebsiteContent records to match the site config"""

from django.core.management import BaseCommand

from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.site_config_api import config_item_iter, has_file_target, is_page_content


class Command(BaseCommand):
    """Updates derived values in WebsiteContent records to match the site config"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-s",
            "--starter-slug",
            dest="starter_slug",
            default="",
            help="If specified, only sync contents for websites that user the given starter.",
        )

    def handle(self, *args, **options):
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
                exit(1)

        updates_performed = False
        for starter in starter_qset:
            sites_updated = 0
            contents_updated = 0
            page_content_config_item_names = []
            other_config_item_names = []
            for config_item in config_item_iter(starter.config):
                if not has_file_target(config_item.item):
                    continue
                if is_page_content(starter.config, config_item.item):
                    page_content_config_item_names.append(config_item.item["name"])
                else:
                    other_config_item_names.append(config_item.item["name"])
            websites = Website.objects.filter(starter=starter)
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
                        f"  Updated {sites_updated} Website(s), {contents_updated} WebsiteContent(s)"
                    )
                )

        if not updates_performed:
            self.stdout.write(
                self.style.WARNING("Data already synced. No updates performed.")
            )
