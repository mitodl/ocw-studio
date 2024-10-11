"""Management command to check the status of Wayback Machine jobs"""

from external_resources.constants import WAYBACK_PENDING_STATUS
from external_resources.models import ExternalResourceState
from external_resources.tasks import check_wayback_jobs_status_batch
from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Check status of Wayback Machine jobs for websites' external resources"""

    help = __doc__

    def handle(self, *args, **options):
        super().handle(*args, **options)

        websites = Website.objects.all()
        websites = self.filter_websites(websites)

        if not websites.exists():
            self.stdout.write("No websites found with the given filters.")
            return

        self.stdout.write(
            f"Checking Wayback Machine job statuses for {websites.count()} websites."
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
            check_wayback_jobs_status_batch.delay(job_ids=job_ids)
            self.stdout.write(
                "Enqueued task to check Wayback Machine job statuses "
                "for filtered websites."
            )
        else:
            check_wayback_jobs_status_batch.delay()
            self.stdout.write(
                "No specific job IDs found. "
                "Enqueued task to check all pending Wayback Machine jobs."
            )

        self.stdout.write("Enqueued task to check Wayback Machine job statuses.")
