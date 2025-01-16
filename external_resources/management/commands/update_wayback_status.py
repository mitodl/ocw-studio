"""Management command to update the status of Wayback Machine jobs"""

from django.conf import settings
from django.core.management.base import CommandError

from external_resources.constants import (
    POSTHOG_ENABLE_WAYBACK_TASKS,
    WAYBACK_PENDING_STATUS,
)
from external_resources.models import ExternalResourceState
from external_resources.tasks import update_wayback_jobs_status_batch
from main.management.commands.filter import WebsiteFilterCommand
from main.posthog import is_feature_enabled
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

        if settings.ENABLE_WAYBACK_TASKS and is_feature_enabled(
            POSTHOG_ENABLE_WAYBACK_TASKS
        ):
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
                f"Updating Wayback Machine job statuses for "
                f"{websites.count()} websites."
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

            if sync_execution:
                self.stdout.write("Running updates synchronously...")
                update_wayback_jobs_status_batch.run(job_ids=job_ids)
            else:
                self.stdout.write(
                    "Enqueuing tasks to update job statuses asynchronously..."
                )
                update_wayback_jobs_status_batch.delay(job_ids=job_ids)

            self.stdout.write("Command execution completed.")
        else:
            self.stdout.write(
                "Wayback Machine tasks are disabled via environment settings "
                "or PostHog feature flag."
            )
            return
