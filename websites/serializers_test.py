""" Tests for websites.serializers """
import pytest
from django.db.models import CharField, Value

from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from users.models import User
from websites.constants import ROLE_EDITOR
from websites.factories import (
    EXAMPLE_SITE_CONFIG,
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
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


def test_website_collaborator_serializer():
    """ WebsiteCollaboratorSerializer should serialize a User object with correct fields """
    website = WebsiteFactory.create()
    collaborator = (
        User.objects.filter(id=UserFactory.create().id)
        .annotate(group=Value(website.editor_group.name, CharField()))
        .first()
    )
    serialized_data = WebsiteCollaboratorSerializer(instance=collaborator).data
    assert serialized_data["username"] == collaborator.username
    assert serialized_data["name"] == collaborator.name
    assert serialized_data["email"] == collaborator.email
    assert serialized_data["group"] == website.editor_group.name
    assert serialized_data["role"] == ROLE_EDITOR


def test_website_content_serializer():
    """WebsiteContentSerializer should serialize a few fields to identify the content"""
    content = WebsiteContentFactory.create()
    serialized_data = WebsiteContentSerializer(instance=content).data
    assert serialized_data["uuid"] == str(content.uuid)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert "markdown" not in serialized_data


def test_website_content_serializer_save():
    """WebsiteContentSerializer should modify only certain fields"""
    content = WebsiteContentFactory.create()
    new_title = f"{content.title} with some more text"
    new_type = f"{content.type}_other"
    # uuid value is invalid but it's ignored since it's marked readonly
    serializer = WebsiteContentSerializer(
        data={"title": new_title, "uuid": "----", "type": new_type}, instance=content
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    content.refresh_from_db()
    assert content.title == new_title
    assert content.type != new_type


def test_website_content_detail_serializer():
    """WebsiteContentDetailSerializer should serialize all relevant fields to the frontend"""
    content = WebsiteContentFactory.create()
    serialized_data = WebsiteContentDetailSerializer(instance=content).data
    assert serialized_data["uuid"] == str(content.uuid)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["markdown"] == content.markdown


def test_website_content_detail_serializer_save():
    """WebsiteContentDetailSerializer should modify only certain fields"""
    content = WebsiteContentFactory.create()
    new_title = f"{content.title} with some more text"
    new_type = f"{content.type}_other"
    new_markdown = "hopefully different from the previous markdown"
    # uuid value is invalid but it's ignored since it's marked readonly
    serializer = WebsiteContentDetailSerializer(
        data={
            "title": new_title,
            "uuid": "----",
            "type": new_type,
            "markdown": new_markdown,
        },
        instance=content,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    content.refresh_from_db()
    assert content.title == new_title
    assert content.type != new_type
    assert content.markdown == new_markdown
