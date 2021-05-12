""" Tests for websites.serializers """
import pytest
from django.db.models import CharField, Value

from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from users.models import User
from websites.constants import (
    CONTENT_TYPE_RESOURCE,
    ROLE_EDITOR,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import WebsiteContent
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteContentCreateSerializer,
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
    starter = WebsiteStarterFactory.build()
    serialized_data = WebsiteStarterDetailSerializer(instance=starter).data
    assert serialized_data["name"] == starter.name
    assert serialized_data["path"] == starter.path
    assert serialized_data["source"] == starter.source
    assert serialized_data["commit"] == starter.commit
    assert "config" in serialized_data
    assert isinstance(serialized_data["config"], dict)


def test_website_detail_deserialize():
    """WebsiteSerializer should deserialize website data"""
    serializer = WebsiteDetailSerializer(
        data={
            "name": "my-site",
            "title": "My Title",
            "source": WEBSITE_SOURCE_OCW_IMPORT,
            "metadata": None,
            "starter": 1,
        }
    )
    assert serializer.is_valid()


@pytest.mark.parametrize("has_starter", [True, False])
def test_website_serializer(has_starter):
    """WebsiteSerializer should serialize a Website object with the correct fields"""
    website = (
        WebsiteFactory.build() if has_starter else WebsiteFactory.build(starter=None)
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
    collaborator = (
        User.objects.filter(id=UserFactory.create().id)
        .annotate(role=Value(ROLE_EDITOR, CharField()))
        .first()
    )
    serialized_data = WebsiteCollaboratorSerializer(instance=collaborator).data
    assert serialized_data["user_id"] == collaborator.id
    assert serialized_data["name"] == collaborator.name
    assert serialized_data["email"] == collaborator.email
    assert serialized_data["role"] == ROLE_EDITOR


def test_website_content_serializer():
    """WebsiteContentSerializer should serialize a few fields to identify the content"""
    content = WebsiteContentFactory.create()
    serialized_data = WebsiteContentSerializer(instance=content).data
    assert serialized_data["text_id"] == str(content.text_id)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert "markdown" not in serialized_data
    assert "metadata" not in serialized_data


def test_website_content_detail_serializer():
    """WebsiteContentDetailSerializer should serialize all relevant fields to the frontend"""
    content = WebsiteContentFactory.create()
    serialized_data = WebsiteContentDetailSerializer(instance=content).data
    assert serialized_data["text_id"] == str(content.text_id)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["markdown"] == content.markdown
    assert serialized_data["metadata"] == content.metadata


def test_website_content_detail_serializer_save(mocker):
    """WebsiteContentDetailSerializer should modify only certain fields"""
    mock_update_website_backend = mocker.patch(
        "websites.serializers.update_website_backend"
    )
    content = WebsiteContentFactory.create(type=CONTENT_TYPE_RESOURCE)
    existing_text_id = content.text_id
    new_title = f"{content.title} with some more text"
    new_type = f"{content.type}_other"
    new_markdown = "hopefully different from the previous markdown"
    metadata = {"description": "data"}
    user = UserFactory.create()
    # uuid value is invalid but it's ignored since it's marked readonly
    serializer = WebsiteContentDetailSerializer(
        data={
            "title": new_title,
            "text_id": "----",
            "type": new_type,
            "markdown": new_markdown,
            "metadata": metadata,
        },
        instance=content,
        context={
            "view": mocker.Mock(kwargs={"parent_lookup_website": content.website.name}),
            "request": mocker.Mock(user=user),
        },
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    content.refresh_from_db()
    assert content.title == new_title
    assert content.text_id == existing_text_id
    assert content.type != new_type
    assert content.markdown == new_markdown
    assert content.metadata == metadata
    assert content.updated_by == user
    mock_update_website_backend.assert_called_once_with(content.website)


@pytest.mark.parametrize("includes_page_content_param", [True, False])
def test_website_content_create_serializer(mocker, includes_page_content_param):
    """WebsiteContentCreateSerializer should create a new WebsiteContent, with some validation"""
    mock_update_website_backend = mocker.patch(
        "websites.serializers.update_website_backend"
    )
    metadata = {"description": "some text"}
    payload = {
        "text_id": "my-text-id",
        "title": "a title",
        "type": CONTENT_TYPE_RESOURCE,
        "markdown": "some markdown",
        "metadata": metadata,
        "is_page_content": False,
    }
    website = WebsiteFactory.create()
    user = UserFactory.create()
    context = {
        "view": mocker.Mock(kwargs={"parent_lookup_website": website.name}),
        "request": mocker.Mock(user=user),
        "website_pk": website.pk,
        **({"is_page_content": True} if includes_page_content_param else {}),
    }
    serializer = WebsiteContentCreateSerializer(data=payload, context=context)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    content = WebsiteContent.objects.get(title=payload["title"])
    mock_update_website_backend.assert_called_once_with(content.website)
    assert content.owner == user
    assert content.updated_by == user
    assert content.title == payload["title"]
    assert content.text_id == payload["text_id"]
    assert content.markdown == payload["markdown"]
    assert content.type == payload["type"]
    assert content.metadata == metadata
    if includes_page_content_param:
        assert content.is_page_content is True
