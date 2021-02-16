""" Tests for websites.serializers """
import pytest

from main.constants import ISO_8601_FORMAT
from websites.factories import (
    EXAMPLE_SITE_CONFIG,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.serializers import (
    WebsiteDetailSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
)


pytestmark = pytest.mark.django_db


def test_serialize_website_course():
    """
    Verify that a serialized website contains expected fields
    """
    site = WebsiteFactory.create()
    serialized_data = WebsiteSerializer(instance=site).data
    assert serialized_data["name"] == site.name
    assert serialized_data["publish_date"] == site.publish_date.strftime(
        ISO_8601_FORMAT
    )
    assert serialized_data["metadata"] == site.metadata
    assert isinstance(serialized_data["starter"], dict)
    assert (
        serialized_data["starter"]
        == WebsiteStarterSerializer(instance=site.starter).data
    )


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
    assert "config" in serialized_data
    assert serialized_data["config"] == EXAMPLE_SITE_CONFIG


@pytest.mark.parametrize("has_starter", [True, False])
def test_website_serializer(has_starter):
    """WebsiteSerializer should serialize a Website object with the correct fields"""
    website = (
        WebsiteFactory.build(starter__config=EXAMPLE_SITE_CONFIG)
        if has_starter
        else WebsiteFactory.build(starter=None)
    )
    serialized_data = WebsiteSerializer(instance=website).data
    assert serialized_data["name"] == website.name
    assert serialized_data["title"] == website.title
    assert serialized_data["metadata"] == website.metadata
    assert "config" not in serialized_data


@pytest.mark.parametrize("has_starter", [True, False])
def test_website_detail_serializer(has_starter):
    """WebsiteDetailSerializer should serialize a Website object with the correct fields, including config"""
    website = (
        WebsiteFactory.build() if has_starter else WebsiteFactory.build(starter=None)
    )
    serialized_data = WebsiteDetailSerializer(instance=website).data
    assert serialized_data["name"] == website.name
    assert serialized_data["title"] == website.title
    assert serialized_data["metadata"] == website.metadata
    assert serialized_data["starter"] == (
        WebsiteStarterDetailSerializer(instance=website.starter).data
        if has_starter
        else None
    )
