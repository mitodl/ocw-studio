""" Backpopulate website groups and permissions"""
from django.core.management import BaseCommand
from django.db.models import Q

from main.utils import now_in_utc
from websites.models import Website
from websites.permissions import create_global_groups, setup_website_groups_permissions


class Command(BaseCommand):
    """ Backpopulate website groups and permissions """

    help = "Backpopulate website groups and permissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--filter",
            dest="filter",
            default="",
            help="If specified, only process websites that contain this filter text in their name",
        )

    def handle(self, *args, **options):

        self.stdout.write(f"Creating website permission groups")
        start = now_in_utc()

        filter_str = options["filter"].lower()
        is_verbose = options["verbosity"] > 1

        total_websites = 0
        total_created = 0
        total_updated = 0
        total_owners = 0

        # Redo global groups too in case permissions changed
        if not filter_str:
            created, updated = create_global_groups()
            self.stdout.write(
                f"Global groups: created {created} groups, updated {updated} groups"
            )

        if filter_str:
            website_qset = Website.objects.filter(
                Q(name__icontains=filter_str) | Q(title__icontains=filter_str)
            )
        else:
            website_qset = Website.objects.all()
        for website in website_qset.iterator():
            created, updated, owner_updated = setup_website_groups_permissions(website)
            total_websites += 1
            total_created += created
            total_updated += updated
            total_owners += 1 if owner_updated else 0

            if is_verbose:
                self.stdout.write(
                    f"{website.name} groups: created {created}, updated {updated}, owner updated: {str(owner_updated)}"
                )

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Creation of website permission groups finished, took {} seconds".format(
                total_seconds
            )
        )
        self.stdout.write(
            f"{total_websites} websites processed, {total_created} groups created, {total_updated} groups updated, {total_owners} updated"
        )
