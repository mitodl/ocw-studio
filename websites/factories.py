""" Factories for websites """
import pytz
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice, FuzzyText

from websites.constants import WEBSITE_TYPE_COURSE
from websites.models import Website


class WebsiteFactory(DjangoModelFactory):
    """Factory for WebsiteFactory"""

    title = FuzzyText()
    url_path = factory.Faker("uri_path")
    uuid = factory.Faker("uuid4")
    type = FuzzyChoice((WEBSITE_TYPE_COURSE, "other"))

    metadata = factory.Faker("json")
    publish_date = factory.Faker("date_time", tzinfo=pytz.utc)

    class Meta:
        model = Website
        django_get_or_create = ("type",)

    class Params:
        is_course = factory.Trait(type=WEBSITE_TYPE_COURSE)
        published = factory.Trait(
            publish_date=factory.Faker("past_datetime", tzinfo=pytz.utc)
        )
        unpublished = factory.Trait(publish_date=None)
        future_publish = factory.Trait(
            publish_date=factory.Faker("future_datetime", tzinfo=pytz.utc)
        )
