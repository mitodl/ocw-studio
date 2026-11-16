"""External Resources Factories"""

import factory
import pytz

from external_resources.models import ExternalResourceState
from websites.factories import WebsiteContentFactory


class ExternalResourceStateFactory(factory.django.DjangoModelFactory):
    """External Resource Factory"""

    class Meta:
        """Meta class for External Resource State Factory"""

        model = ExternalResourceState

    content = factory.SubFactory(WebsiteContentFactory)
    status = factory.Iterator(["unchecked", "valid", "broken", "check_failed"])
    last_checked = factory.Faker("date_time", tzinfo=pytz.utc)
    external_url_response_code = factory.Faker("random_int", min=100, max=599)
    wayback_job_id = factory.Faker("uuid4")
    wayback_status = factory.Iterator(ExternalResourceState.WaybackStatus.values)
    wayback_url = factory.Faker("url")
    wayback_status_ext = factory.Faker("sentence")
    wayback_http_status = factory.Faker("random_int", min=100, max=599)
    # Keep this well outside WAYBACK_SUBMISSION_INTERVAL_DAYS (30 by default).
    # A random date since 1970 landed in the last 30 days about 1 time in 700,
    # and submit_url_to_wayback_task then skipped the resource as recently
    # submitted.
    wayback_last_successful_submission = factory.Faker(
        "date_time_between", start_date="-10y", end_date="-1y", tzinfo=pytz.utc
    )
