""" Factories for websites """
from pathlib import Path

import factory
import pytz
import yaml
from django.conf import settings
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from users.factories import UserFactory
from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE, STARTER_SOURCES
from websites.models import (
    Website,
    WebsiteCollection,
    WebsiteCollectionItem,
    WebsiteContent,
    WebsiteStarter,
)


FACTORY_SITE_CONFIG_PATH = "localdev/configs/basic-site-config.yml"


class WebsiteStarterFactory(DjangoModelFactory):
    """Factory for WebsiteStarter"""

    path = factory.Faker("uri")
    name = factory.Faker("domain_word")
    slug = factory.Sequence(lambda n: "starter-%x" % n)
    source = FuzzyChoice(STARTER_SOURCES)
    commit = factory.Faker("md5")
    config = factory.LazyAttribute(
        lambda _: yaml.load(
            (Path(settings.BASE_DIR) / FACTORY_SITE_CONFIG_PATH).read_text(),
            Loader=yaml.SafeLoader,
        )
    )

    class Meta:
        model = WebsiteStarter


class WebsiteFactory(DjangoModelFactory):
    """Factory for Website"""

    title = factory.Sequence(lambda n: "Site %s" % n)
    name = factory.Sequence(lambda n: "site-%s" % n)
    short_id = factory.Sequence(lambda n: "site-%s" % n)
    metadata = factory.Faker("json")
    publish_date = factory.Faker("date_time", tzinfo=pytz.utc)
    draft_publish_date = factory.Faker("date_time", tzinfo=pytz.utc)
    starter = factory.SubFactory(WebsiteStarterFactory)
    owner = factory.SubFactory(UserFactory)
    gdrive_folder = factory.Faker("md5")

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

    title = factory.Sequence(lambda n: "OCW Site Content %s" % n)
    type = FuzzyChoice([CONTENT_TYPE_PAGE, CONTENT_TYPE_RESOURCE])
    markdown = factory.Faker("text")
    metadata = factory.Faker("json")
    filename = factory.Sequence(lambda n: "my-file-%s" % n)
    dirpath = factory.Faker("uri_path", deep=2)
    website = factory.SubFactory(WebsiteFactory)

    class Meta:
        model = WebsiteContent


class WebsiteCollectionFactory(DjangoModelFactory):
    """Factory for WebsiteCollection"""

    title = factory.Sequence(lambda n: "WebsiteCollection %s" % n)
    description = factory.Faker("text")

    class Meta:
        model = WebsiteCollection


class WebsiteCollectionItemFactory(DjangoModelFactory):
    """Factory for WebsiteCollectionItem"""

    website_collection = factory.SubFactory(WebsiteCollectionFactory)
    website = factory.SubFactory(WebsiteFactory)
    position = factory.Sequence(lambda n: n)

    class Meta:
        model = WebsiteCollectionItem
