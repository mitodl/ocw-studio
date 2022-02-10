""" Tests for websites.serializers """
import pytest
from dateutil.parser import parse as parse_date
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import CharField, Value

from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from users.models import User
from videos.constants import YT_THUMBNAIL_IMG
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
from websites.models import WebsiteContent, WebsiteStarter
from websites.serializers import (
    WebsiteCollaboratorSerializer,
    WebsiteContentCreateSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
    WebsiteDetailSerializer,
    WebsitePublishSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
    WebsiteStatusSerializer,
)
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db


def test_serialize_website_course():
    """
    Verify that a serialized website contains expected fields
    """
    site = WebsiteFactory.create()
    serialized_data = WebsiteSerializer(instance=site).data
    assert serialized_data["name"] == site.name
    assert serialized_data["short_id"] == site.short_id
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
            "short_id": "my-title",
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


@pytest.mark.parametrize("warnings", [[], ["error1", "error2"]])
@pytest.mark.parametrize("drive_folder", [None, "abc123"])
def test_website_status_serializer(mocker, settings, drive_folder, warnings):
    """WebsiteStatusSerializer should serialize a Website object with the correct status fields"""
    mocker.patch(
        "websites.serializers.incomplete_content_warnings", return_value=warnings
    )
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "dfg789"
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = {"key": "value"}
    settings.DRIVE_SHARED_ID = "abc123"
    values = {
        "publish_date": "2021-11-01T00:00:00Z",
        "draft_publish_date": "2021-11-02T00:00:00Z",
        "has_unpublished_live": True,
        "has_unpublished_draft": False,
        "live_publish_status": "succeeded",
        "live_publish_status_updated_on": "2021-11-03T00:00:00Z",
        "draft_publish_status": "errored",
        "draft_publish_status_updated_on": "2021-11-04T00:00:00Z",
        "sync_status": "Complete",
        "sync_errors": ["error1"],
        "synced_on": "2021-11-05T00:00:00Z",
    }
    website = WebsiteFactory.build(gdrive_folder=drive_folder, **values)
    serialized_data = WebsiteStatusSerializer(instance=website).data
    assert serialized_data["gdrive_url"] == (
        f"https://drive.google.com/drive/folders/{settings.DRIVE_UPLOADS_PARENT_FOLDER_ID}/{website.gdrive_folder}"
        if drive_folder is not None
        else None
    )
    assert sorted(serialized_data["content_warnings"]) == sorted(warnings)
    for (key, value) in values.items():
        assert serialized_data.get(key) == value


@pytest.mark.parametrize("has_starter", [True, False])
@pytest.mark.parametrize("drive_folder", [None, "abc123"])
@pytest.mark.parametrize("drive_credentials", [None, {"creds: True"}])
def test_website_detail_serializer(
    settings, has_starter, drive_folder, drive_credentials
):
    """WebsiteDetailSerializer should serialize a Website object with the correct fields, including config"""
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = drive_credentials
    settings.DRIVE_SHARED_ID = "abc123"
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = None
    website = WebsiteFactory.build(
        gdrive_folder=drive_folder,
        starter=(WebsiteStarterFactory.create() if has_starter else None),
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
    assert serialized_data["source"] == website.source
    assert parse_date(serialized_data["publish_date"]) == website.publish_date
    assert (
        parse_date(serialized_data["draft_publish_date"]) == website.draft_publish_date
    )
    assert serialized_data["live_url"] == website.get_url("live")
    assert serialized_data["draft_url"] == website.get_url("draft")
    assert serialized_data["has_unpublished_live"] == website.has_unpublished_live
    assert serialized_data["has_unpublished_draft"] == website.has_unpublished_draft
    assert serialized_data["gdrive_url"] == (
        f"https://drive.google.com/drive/folders/abc123/{website.gdrive_folder}"
        if drive_credentials is not None and drive_folder is not None
        else None
    )


@pytest.mark.parametrize("user_is_admin", [True, False])
@pytest.mark.parametrize("has_user", [True, False])
def test_website_detail_serializer_is_admin(mocker, user_is_admin, has_user):
    """is_admin should be true or false depending on the user status"""
    is_site_admin_mock = mocker.patch(
        "websites.serializers.is_site_admin", return_value=user_is_admin
    )
    user = UserFactory.create()
    website = WebsiteFactory.create()
    serialized = WebsiteDetailSerializer(
        instance=website,
        context={"request": mocker.Mock(user=user if has_user else None)},
    ).data
    assert serialized["is_admin"] == (user_is_admin and has_user)
    if has_user:
        is_site_admin_mock.assert_called_once_with(user, website)


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
    assert serialized_data["updated_on"] == content.updated_on.isoformat()[:-6] + "Z"
    assert "markdown" not in serialized_data
    assert "metadata" not in serialized_data


def test_website_content_detail_serializer():
    """WebsiteContentDetailSerializer should serialize all relevant fields to the frontend"""
    content = WebsiteContentFactory.create()
    serialized_data = WebsiteContentDetailSerializer(instance=content).data
    assert serialized_data["text_id"] == str(content.text_id)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["updated_on"] == content.updated_on.isoformat()[:-6] + "Z"
    assert serialized_data["markdown"] == content.markdown
    assert serialized_data["metadata"] == content.metadata


@pytest.mark.parametrize("is_resource", [True, False])
def test_website_content_detail_serializer_youtube_ocw(settings, is_resource):
    """WebsiteContent serializers should conditionally fill in youtube thumbnail metadata"""
    settings.OCW_IMPORT_STARTER_SLUG = "course"
    starter = WebsiteStarter.objects.get(slug=settings.OCW_IMPORT_STARTER_SLUG)
    website = WebsiteFactory.create(starter=starter)
    youtube_id = "abc123"
    content_type = "resource" if is_resource else "page"
    existing_content = WebsiteContentFactory.create(
        type=content_type,
        website=website,
    )
    data = (
        {
            "metadata": {
                "video_metadata": {"youtube_id": youtube_id},
                "video_files": {"video_thumbnail_file": ""},
            },
        }
        if is_resource
        else {"metadata": {"body": "text"}}
    )
    existing_serializer = WebsiteContentDetailSerializer()
    existing_serializer.update(existing_content, data)

    data["type"] = content_type
    data["title"] = "new content"
    new_serializer = WebsiteContentCreateSerializer()
    new_serializer.context["website_id"] = website.uuid
    new_content = new_serializer.create(data)

    for content in [existing_content, new_content]:
        if is_resource:
            assert content.metadata["video_metadata"]["youtube_id"] == youtube_id
            assert content.metadata["video_files"][
                "video_thumbnail_file"
            ] == YT_THUMBNAIL_IMG.format(video_id=youtube_id)
        else:
            assert content.metadata["body"] == "text"


def test_website_content_detail_with_file_serializer():
    """WebsiteContentDetailSerializer should include its file url in metadata"""
    content = WebsiteContentFactory.create(type="resource", metadata={"title": "Test"})
    content.file = SimpleUploadedFile("test.txt", b"content")

    serialized_data = WebsiteContentDetailSerializer(instance=content).data
    assert serialized_data["image"] == content.file.url
    assert serialized_data["metadata"]["title"] == content.metadata["title"]


@pytest.mark.parametrize("content_context", [True, False])
@pytest.mark.parametrize("multiple", [True, False])
@pytest.mark.parametrize("cross_site", [True, False])
@pytest.mark.parametrize("invalid_data", [True, False])
@pytest.mark.parametrize("nested", [True, False])
@pytest.mark.parametrize("field_order_reversed", [True, False])
def test_website_content_detail_serializer_content_context(  # pylint:disable=too-many-arguments,too-many-locals
    content_context, multiple, cross_site, invalid_data, nested, field_order_reversed
):
    """WebsiteContentDetailSerializer should serialize content_context for relation and menu fields"""
    relation_field = {
        "name": "relation_field_name",
        "label": "Relation field label",
        "multiple": multiple,
        "global": cross_site,
        "widget": "relation",
    }
    menu_field = {
        "name": "menu_field_name",
        "label": "Menu field label",
        "widget": "menu",
    }
    field_list = [menu_field, relation_field]
    if field_order_reversed:
        field_list = list(reversed(field_list))
    website = WebsiteFactory.create(
        starter__config={
            "collections": [
                {
                    "fields": [{"name": "outer", "fields": field_list}]
                    if nested
                    else field_list
                }
            ]
        }
    )
    menu_referenced = WebsiteContentFactory.create(website=website)
    relation_referenced = WebsiteContentFactory.create()
    referenced_list = [menu_referenced, relation_referenced]
    if field_order_reversed:
        referenced_list = list(reversed(referenced_list))
    for content in referenced_list:
        # These have the same text_id but a different website so it should not match and therefore be ignored
        WebsiteContentFactory.create(text_id=content.text_id)

    relation_content = relation_referenced.text_id
    if multiple:
        relation_content = [relation_referenced.text_id]
    elif cross_site:
        relation_content = [
            [relation_referenced.text_id, relation_referenced.website.name]
        ]

    metadata = {
        relation_field["name"]: {
            "content": relation_content,
            "website": relation_referenced.website.name,
        },
        menu_field["name"]: [
            {
                "identifier": "external-not-a-match",
            },
            {"identifier": "uuid-not-found-so-ignored"},
            {
                "identifier": menu_referenced.text_id,
            },
        ],
    }
    if invalid_data:
        metadata = {}
    elif nested:
        metadata = {"outer": metadata}

    content = WebsiteContentFactory.create(website=website, metadata=metadata)
    serialized_data = WebsiteContentDetailSerializer(
        instance=content, context={"content_context": content_context}
    ).data
    assert serialized_data["text_id"] == str(content.text_id)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["markdown"] == content.markdown
    assert serialized_data["metadata"] == content.metadata
    assert serialized_data["content_context"] == (
        (
            []
            if invalid_data
            else WebsiteContentDetailSerializer(
                instance=referenced_list, many=True, context={"content_context": False}
            ).data
        )
        if content_context
        else None
    )


def test_website_content_detail_serializer_save(mocker):
    """WebsiteContentDetailSerializer should modify only certain fields"""
    mock_update_website_backend = mocker.patch(
        "websites.serializers.update_website_backend"
    )
    mock_create_website_pipeline = mocker.patch(
        "websites.serializers.create_website_publishing_pipeline"
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
    mock_create_website_pipeline.assert_not_called()


@pytest.mark.parametrize("add_context_data", [True, False])
def test_website_content_create_serializer(mocker, add_context_data):
    """
    WebsiteContentCreateSerializer should create a new WebsiteContent object, using context data as an override
    if extra context data is passed in.
    """
    mock_update_website_backend = mocker.patch(
        "websites.serializers.update_website_backend"
    )
    website = WebsiteFactory.create()
    user = UserFactory.create()
    metadata = {"description": "some text"}
    payload = {
        "website_id": website.pk,
        "text_id": "my-text-id",
        "title": "a title",
        "type": CONTENT_TYPE_RESOURCE,
        "markdown": "some markdown",
        "metadata": metadata,
        "is_page_content": False,
        "dirpath": "path/to",
        "filename": "myfile",
    }
    override_context_data = (
        {}
        if not add_context_data
        else {
            "is_page_content": True,
            "dirpath": "override/path",
            "filename": "overridden-filename",
        }
    )
    context = {
        "view": mocker.Mock(kwargs={"parent_lookup_website": website.name}),
        "request": mocker.Mock(user=user),
        "website_id": website.pk,
        **override_context_data,
    }
    serializer = WebsiteContentCreateSerializer(data=payload, context=context)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    content = WebsiteContent.objects.get(title=payload["title"])
    mock_update_website_backend.assert_called_once_with(content.website)
    assert content.website_id == website.pk
    assert content.owner == user
    assert content.updated_by == user
    assert content.title == payload["title"]
    assert content.text_id == payload["text_id"]
    assert content.markdown == payload["markdown"]
    assert content.type == payload["type"]
    assert content.metadata == metadata
    assert content.is_page_content is (
        False if not add_context_data else override_context_data["is_page_content"]
    )
    assert content.dirpath == (
        "path/to" if not add_context_data else override_context_data["dirpath"]
    )
    assert content.filename == (
        "myfile" if not add_context_data else override_context_data["filename"]
    )


@pytest.mark.parametrize("is_root_site", [True, False])
def test_website_publish_serializer_base_url(settings, is_root_site):
    """ The WebsitePublishSerializer should return the correct base_url value """
    site = WebsiteFactory.create()
    site_config = SiteConfig(site.starter.config)
    settings.ROOT_WEBSITE_NAME = site.name if is_root_site else "some_other_root_name"
    serializer = WebsitePublishSerializer(site)
    assert serializer.data["base_url"] == (
        "" if is_root_site else f"{site_config.root_url_path}/{site.name}".strip("/")
    )
