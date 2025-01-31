"""Management command to submit external resources to the Wayback Machine"""

from django.conf import settings

from external_resources.constants import POSTHOG_ENABLE_WAYBACK_TASKS
from external_resources.tasks import submit_website_resources_to_wayback_task
from main.management.commands.filter import WebsiteFilterCommand
from main.posthog import is_feature_enabled
from websites.models import Website


class Command(WebsiteFilterCommand):
    """Submit external resources to the Wayback Machine"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force submission even if resources were submitted recently.",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)

        if settings.ENABLE_WAYBACK_TASKS and is_feature_enabled(
            POSTHOG_ENABLE_WAYBACK_TASKS
        ):
            force_submission = options.get("force", False)

            websites = Website.objects.all()
            websites = self.filter_websites(websites)

            if not websites.exists():
                self.stdout.write("No websites found with the given filters.")
                return

            self.stdout.write(
                f"Submitting external resources for {websites.count()} websites."
            )

            for website in websites:
                submit_website_resources_to_wayback_task.delay(
                    website.name, ignore_last_submission=force_submission
                )
                self.stdout.write(f"Enqueued submission for website: {website.name}")

            self.stdout.write("All tasks have been enqueued.")
        else:
            self.stdout.write(
                "Wayback Machine tasks are disabled via environment settings "
                "or PostHog feature flag."
            )
            return
