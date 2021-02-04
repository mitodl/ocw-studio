""" Tests for websites.serializers """
import pytest
import yaml

from main.constants import ISO_8601_FORMAT
from websites.constants import WEBSITE_TYPE_COURSE
from websites.factories import (
    WebsiteFactory,
    WebsiteStarterFactory,
    EXAMPLE_SITE_CONFIG,
)
from websites.serializers import (
    WebsiteSerializer,
    WebsiteStarterSerializer,
    WebsiteStarterDetailSerializer,
)


@pytest.mark.django_db
def test_serialize_website_course():
    """
    Verify that a serialized website contains expected fields
    """
    site = WebsiteFactory(is_course=True)
    serializer = WebsiteSerializer(site)
    assert serializer.data["type"] == WEBSITE_TYPE_COURSE
    assert serializer.data["url_path"] == site.url_path
    assert serializer.data["publish_date"] == site.publish_date.strftime(
        ISO_8601_FORMAT
    )
    assert serializer.data["metadata"] == site.metadata


def test_website_starter_serializer():
    """WebsiteStarterSerializer should serialize a WebsiteStarter object with the correct fields"""
    starter = WebsiteStarterFactory.build()
    serialized_data = WebsiteStarterSerializer(instance=starter).data
    assert serialized_data["name"] == starter.name
    assert serialized_data["path"] == starter.path
    assert serialized_data["source"] == starter.source
    assert serialized_data["commit"] == starter.commit
    assert "config" not in serialized_data


def test_website_starter_detail_serializer():
    """WebsiteStarterDetailSerializer should serialize a WebsiteStarter object with the correct fields"""
    starter = WebsiteStarterFactory.build(config=EXAMPLE_SITE_CONFIG)
    serialized_data = WebsiteStarterDetailSerializer(instance=starter).data
    assert serialized_data["name"] == starter.name
    assert serialized_data["path"] == starter.path
    assert serialized_data["source"] == starter.source
    assert serialized_data["commit"] == starter.commit
    assert serialized_data["config"] == yaml.load(
        EXAMPLE_SITE_CONFIG, Loader=yaml.Loader
    )
