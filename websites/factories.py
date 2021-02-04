""" Factories for websites """
import pytz
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from websites.constants import WEBSITE_TYPE_COURSE, STARTER_SOURCES
from websites.models import Website, WebsiteStarter

EXAMPLE_SITE_CONFIG = """
collections:
  - label: "Page"
    name: "page"
    fields:
      - {label: "Title", name: "title", widget: "string"}
"""


class WebsiteFactory(DjangoModelFactory):
    """Factory for Website"""

    title = factory.Sequence(lambda n: "OCW Course %s" % n)
    url_path = factory.Sequence(lambda n: "/ocw_site_x/%s" % n)
    type = FuzzyChoice((WEBSITE_TYPE_COURSE, "other"))

    metadata = factory.Faker("json")
    publish_date = factory.Faker("date_time", tzinfo=pytz.utc)

    class Meta:
        model = Website

    class Params:
        is_course = factory.Trait(type=WEBSITE_TYPE_COURSE)
        not_course = factory.Trait(type="other")
        published = factory.Trait(
            publish_date=factory.Faker("past_datetime", tzinfo=pytz.utc)
        )
        unpublished = factory.Trait(publish_date=None)
        future_publish = factory.Trait(
            publish_date=factory.Faker("future_datetime", tzinfo=pytz.utc)
        )


class WebsiteStarterFactory(DjangoModelFactory):
    """Factory for WebsiteStarter"""

    path = factory.Faker("uri")
    name = factory.Faker("domain_word")
    source = factory.fuzzy.FuzzyChoice(STARTER_SOURCES)
    commit = factory.Faker("md5")
    config = EXAMPLE_SITE_CONFIG

    class Meta:
        model = WebsiteStarter
