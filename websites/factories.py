""" Factories for websites """
import pytz
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_FILE, STARTER_SOURCES
from websites.models import WebsiteStarter, WebsiteContent, Website

EXAMPLE_SITE_CONFIG = {
    "collections": [
        {
            "fields": [
                {"label": "Title", "name": "title", "widget": "string"},
                {"label": "Body", "name": "body", "widget": "markdown"},
            ],
            "label": "Page",
            "name": "page",
        }
    ]
}


class WebsiteStarterFactory(DjangoModelFactory):
    """Factory for WebsiteStarter"""

    path = factory.Faker("uri")
    name = factory.Faker("domain_word")
    slug = factory.Sequence(lambda n: "starter-%x" % n)
    source = FuzzyChoice(STARTER_SOURCES)
    commit = factory.Faker("md5")
    config = EXAMPLE_SITE_CONFIG

    class Meta:
        model = WebsiteStarter


class WebsiteFactory(DjangoModelFactory):
    """Factory for Website"""

    title = factory.Sequence(lambda n: "Site %s" % n)
    name = factory.Sequence(lambda n: "site-%s" % n)
    metadata = factory.Faker("json")
    publish_date = factory.Faker("date_time", tzinfo=pytz.utc)
    starter = factory.SubFactory(WebsiteStarterFactory)

    class Meta:
        model = Website

    class Params:
        published = factory.Trait(
            publish_date=factory.Faker("past_datetime", tzinfo=pytz.utc)
        )
        unpublished = factory.Trait(publish_date=None)
        future_publish = factory.Trait(
            publish_date=factory.Faker("future_datetime", tzinfo=pytz.utc)
        )


class WebsiteContentFactory(DjangoModelFactory):
    """Factory for WebsiteContent"""

    title = factory.Sequence(lambda n: "OCW Course Content %s" % n)
    type = FuzzyChoice((CONTENT_TYPE_PAGE, CONTENT_TYPE_FILE))
    markdown = factory.Faker("text")
    metadata = factory.Faker("json")
    hugo_filepath = factory.Sequence(lambda n: "/courses/ocw_site_x/%s" % n)

    website = factory.SubFactory(WebsiteFactory)

    class Meta:
        model = WebsiteContent
