""" Factories for websites """
from pathlib import Path

import factory
import pytz
import yaml
from django.conf import settings
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from users.factories import UserFactory
from websites import constants
from websites.models import Website, WebsiteContent, WebsiteStarter


FACTORY_SITE_CONFIG_PATH = "localdev/configs/basic-site-config.yml"


class WebsiteStarterFactory(DjangoModelFactory):
    """Factory for WebsiteStarter"""

    path = factory.Faker("uri")
    name = factory.Faker("domain_word")
    status = factory.Faker(constants.WebsiteStarterStatus.ACTIVE)
    slug = factory.Sequence(lambda n: "starter-%x" % n)
    source = FuzzyChoice(constants.STARTER_SOURCES)
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
    name = factory.Sequence(lambda n: "site-name-%s" % n)
    url_path = factory.Sequence(lambda n: "courses/site-path-%s" % n)
    short_id = factory.Sequence(lambda n: "site-shortid-%s" % n)
    metadata = factory.Faker("json")
    publish_date = factory.Faker("date_time", tzinfo=pytz.utc)
    first_published_to_production = factory.Faker("date_time", tzinfo=pytz.utc)
    draft_publish_date = factory.Faker("date_time", tzinfo=pytz.utc)
    unpublish_status = None
    starter = factory.SubFactory(WebsiteStarterFactory)
    owner = factory.SubFactory(UserFactory)
    gdrive_folder = factory.Faker("md5")

    class Meta:
        model = Website

    class Params:
        with_url_path = factory.Trait(
            url_path=factory.Sequence(lambda n: "courses/site-path-%s" % n)
        )
        published = factory.Trait(
            publish_date=factory.Faker("past_datetime", tzinfo=pytz.utc),
            first_published_to_production=factory.Faker(
                "past_datetime", tzinfo=pytz.utc
            ),
            unpublish_status=None,
        )
        not_published = factory.Trait(
            publish_date=None, first_published_to_production=None
        )
        unpublished = factory.Trait(
            publish_date=factory.Faker("past_datetime", tzinfo=pytz.utc),
            first_published_to_production=factory.Faker(
                "past_datetime", tzinfo=pytz.utc
            ),
            unpublish_status=FuzzyChoice(
                [
                    constants.PUBLISH_STATUS_PENDING,
                    constants.PUBLISH_STATUS_STARTED,
                    constants.PUBLISH_STATUS_ERRORED,
                    constants.PUBLISH_STATUS_ABORTED,
                    constants.PUBLISH_STATUS_NOT_STARTED,
                ]
            ),
        )
        future_publish = factory.Trait(
            publish_date=factory.Faker("future_datetime", tzinfo=pytz.utc),
            first_published_to_production=factory.Faker(
                "future_datetime", tzinfo=pytz.utc
            ),
        )


class WebsiteContentFactory(DjangoModelFactory):
    """Factory for WebsiteContent"""

    title = factory.Sequence(lambda n: "OCW Site Content %s" % n)
    type = FuzzyChoice([constants.CONTENT_TYPE_PAGE, constants.CONTENT_TYPE_RESOURCE])
    markdown = factory.Faker("text")
    metadata = factory.LazyAttribute(lambda _: {})
    filename = factory.Sequence(lambda n: "my-file-%s" % n)
    dirpath = factory.Faker("uri_path", deep=2)
    website = factory.SubFactory(WebsiteFactory)

    class Meta:
        model = WebsiteContent
