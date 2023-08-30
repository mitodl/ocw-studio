"""Backpopulate website groups and permissions"""  # noqa: INP001
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website
from websites.permissions import create_global_groups, setup_website_groups_permissions


class Command(WebsiteFilterCommand):
    """Backpopulate website groups and permissions"""

    help = "Backpopulate website groups and permissions"  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--only-global",
            dest="only-global",
            action="store_true",
            help=("If true, only update global groups"),
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        self.stdout.write("Creating website permission groups")
        start = now_in_utc()

        is_verbose = options["verbosity"] > 1

        total_websites = 0
        total_created = 0
        total_updated = 0
        total_owners = 0

        # Redo global groups too in case permissions changed
        if not self.filter_list:
            created, updated = create_global_groups()
            self.stdout.write(
                f"Global groups: created {created} groups, updated {updated} groups"
            )

        if not options["only-global"]:
            if self.filter_list:
                website_qset = Website.objects.filter(
                    Q(name__in=self.filter_list)
                    | Q(short_id__icontains=self.filter_list)
                )
            else:
                website_qset = Website.objects.all()
            for website in website_qset.iterator():
                created, updated, owner_updated = setup_website_groups_permissions(
                    website
                )
                total_websites += 1
                total_created += created
                total_updated += updated
                total_owners += 1 if owner_updated else 0

                if is_verbose:
                    self.stdout.write(
                        f"{website.name} groups: created {created}, updated {updated}, owner updated: {owner_updated!s}"  # noqa: E501
                    )

            total_seconds = (now_in_utc() - start).total_seconds()
            self.stdout.write(
                "Creation of website permission groups finished, took {} seconds".format(  # noqa: E501
                    total_seconds
                )
            )
            self.stdout.write(
                f"{total_websites} websites processed, {total_created} groups created, {total_updated} groups updated, {total_owners} updated"  # noqa: E501
            )
