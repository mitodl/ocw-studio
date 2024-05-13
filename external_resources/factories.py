import factory
import pytz

from external_resources.models import ExternalResourceState
from websites.factories import WebsiteContentFactory


class ExternalResourceStateFactory(factory.django.DjangoModelFactory):
    """External Resource Factory"""

    class Meta:
        model = ExternalResourceState

    content = factory.SubFactory(WebsiteContentFactory)
    status = ExternalResourceState.Status.UNCHECKED
    external_url_response_code = factory.Faker("random_int", min=100, max=599)
    backup_url_response_code = factory.Faker("random_int", min=100, max=599)
    is_external_url_broken = factory.Faker("boolean")
    is_backup_url_broken = factory.Faker("boolean")
    last_checked = factory.Faker("date_time", tzinfo=pytz.utc)
