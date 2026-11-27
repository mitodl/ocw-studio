"""Factories for websites"""

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


def site_config_with_resource_languages(*codes: str) -> dict:
    """
    Return the factory site config with a "language" select on the resource
    item, offering these language codes, as the OCW course starter has.
    """
    config = yaml.load(
        (Path(settings.BASE_DIR) / FACTORY_SITE_CONFIG_PATH).read_text(),
        Loader=yaml.SafeLoader,
    )
    resource_item = next(
        item
        for item in config["collections"]
        if item["name"] == constants.CONTENT_TYPE_RESOURCE
    )
    resource_item["fields"].append(
        {
            "label": "Language",
            "name": "language",
            "widget": "select",
            "options": [{"label": code, "value": code} for code in codes],
        }
    )
    return config


class WebsiteStarterFactory(DjangoModelFactory):
    """Factory for WebsiteStarter"""

    path = factory.Faker("uri")
    name = factory.Faker("domain_word")
    status = FuzzyChoice(constants.WebsiteStarterStatus.ALL_STATUSES)
    slug = factory.Sequence(lambda n: f"starter-{n}")
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

    title = factory.Sequence(lambda n: f"Site {n}")
    name = factory.Sequence(lambda n: f"site-name-{n}")
    url_path = factory.Sequence(lambda n: f"courses/site-path-{n}")
    short_id = factory.Sequence(lambda n: f"site-shortid-{n}")
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
            url_path=factory.Sequence(lambda n: f"courses/site-path-{n}")
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

    title = factory.Sequence(lambda n: f"OCW Site Content {n}")
    type = FuzzyChoice([constants.CONTENT_TYPE_PAGE, constants.CONTENT_TYPE_RESOURCE])
    markdown = factory.Faker("text")
    metadata = factory.LazyAttribute(lambda _: {})
    filename = factory.Sequence(lambda n: f"my-file-{n}_ext")
    dirpath = factory.Faker("uri_path", deep=2)
    website = factory.SubFactory(WebsiteFactory)

    class Meta:
        model = WebsiteContent


def create_video_resource(
    website, filename, youtube_id=None, captions=None, transcripts=None
):
    """
    Create a Video resource, optionally with a YouTube id and with caption and
    transcript ids linked. Pass a string to store a legacy bare id relation.
    """
    video_files = {}
    if captions is not None:
        video_files["video_captions_resources"] = {
            "content": captions,
            "website": website.name,
        }
    if transcripts is not None:
        video_files["video_transcript_resources"] = {
            "content": transcripts,
            "website": website.name,
        }
    metadata = {
        "resourcetype": constants.RESOURCE_TYPE_VIDEO,
        "video_files": video_files,
    }
    if youtube_id is not None:
        metadata["video_metadata"] = {"youtube_id": youtube_id}
    return WebsiteContentFactory.create(
        website=website,
        type=constants.CONTENT_TYPE_RESOURCE,
        filename=filename,
        metadata=metadata,
    )
