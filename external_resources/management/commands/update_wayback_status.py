"""Management command to update the status of Wayback Machine jobs"""

from django.core.management.base import CommandError

from external_resources.constants import WAYBACK_PENDING_STATUS
from external_resources.models import ExternalResourceState
from external_resources.tasks import update_wayback_jobs_status_batch
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Update status of Wayback Machine pending jobs"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run the updates synchronously instead of queuing tasks.",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        sync_execution = options.get("sync", False)

        websites = Website.objects.all()
        websites = self.filter_websites(websites)

        if not websites.exists():
            self.stdout.write("No websites found with the given filters.")
            return

        if sync_execution and not options.get("filter"):
            message = "The --sync option requires website filters to be specified."
            raise CommandError(message)

        self.stdout.write(
            f"Updating Wayback Machine job statuses for {websites.count()} websites."
        )

        # Get ExternalResourceState objects with pending Wayback jobs
        pending_states = ExternalResourceState.objects.filter(
            content__website__in=websites,
            wayback_status=WAYBACK_PENDING_STATUS,
            wayback_job_id__isnull=False,
        )

        if not pending_states.exists():
            self.stdout.write(
                "No pending Wayback Machine jobs found for the selected websites."
            )
            return

        job_ids = list(pending_states.values_list("wayback_job_id", flat=True))

        if job_ids:
            update_wayback_jobs_status_batch.delay(job_ids=job_ids)
            self.stdout.write(
                "Enqueued task to update Wayback Machine job statuses "
                "for filtered websites."
            )
        else:
            update_wayback_jobs_status_batch.delay()
            self.stdout.write(
                "No specific job IDs found. "
                "Enqueued task to update all pending Wayback Machine jobs."
            )

        self.stdout.write("Enqueued task to check Wayback Machine job statuses.")
