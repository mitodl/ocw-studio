"""Tests for websites.serializers"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from dateutil.parser import parse as parse_date
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import CharField, Value
from mitol.common.utils import now_in_utc

from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from users.models import User
from videos.constants import YT_THUMBNAIL_IMG
from websites.constants import (
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_RESOURCE,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
    ROLE_EDITOR,
    WEBSITE_CONFIG_ROOT_URL_PATH_KEY,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import WebsiteContent, WebsiteStarter
from websites.serializers import (
    ExportWebsiteContentSerializer,
    ExportWebsiteSerializer,
    WebsiteCollaboratorSerializer,
    WebsiteContentCreateSerializer,
    WebsiteContentDetailSerializer,
    WebsiteContentSerializer,
    WebsiteDetailSerializer,
    WebsiteMassBuildSerializer,
    WebsiteSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
    WebsiteStatusSerializer,
    WebsiteUnpublishSerializer,
    WebsiteUrlSerializer,
)
from websites.site_config_api import SiteConfig

pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name


@pytest.fixture()
def mocked_website_funcs(mocker):
    """Mocked website-related functions"""  # noqa: D401
    return SimpleNamespace(
        update_website_backend=mocker.patch(
            "websites.serializers.update_website_backend"
        ),
    )


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


def test_serialize_basic_website_course():
    """
    Verify that a serialized basic website contains expected fields
    """
    site = WebsiteFactory.create()
    serialized_data = WebsiteSerializer(instance=site).data
    assert serialized_data["name"] == site.name
    assert serialized_data["title"] == site.title


def test_website_starter_serializer():
    """WebsiteStarterSerializer should serialize a WebsiteStarter object with the correct fields"""
    starter = WebsiteStarterFactory.build()
    serialized_data = WebsiteStarterSerializer(instance=starter).data
    assert serialized_data["name"] == starter.name
    assert serialized_data["status"] == starter.status
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
    mocker.patch("websites.serializers.get_content_warnings", return_value=warnings)
    settings.DRIVE_UPLOADS_PARENT_FOLDER_ID = "dfg789"
    settings.DRIVE_SERVICE_ACCOUNT_CREDS = {"key": "value"}
    settings.DRIVE_SHARED_ID = "abc123"
    values = {
        "title": "site title",
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
    for key, value in values.items():
        assert serialized_data.get(key) == value


EXAMPLE_METADATA = {
    "term": "",
    "year": "",
    "level": [],
    "topics": [],
    "legacy_uid": "",
    "instructors": {
        "content": [],
        "website": "jens-test-site-for-video-resource-icons",
    },
}


@pytest.mark.parametrize("metadata", [EXAMPLE_METADATA, {}])
def test_website_content_has_metadata(mocker, metadata):
    website = WebsiteFactory.create()
    bool(metadata) and WebsiteContentFactory.create(
        type="sitemetadata", website=website, metadata=metadata
    )
    serialized_data = WebsiteStatusSerializer(instance=website).data
    assert serialized_data["has_site_metadata"] == bool(metadata)


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
    assert serialized_data["live_url"] == website.get_full_url("live")
    assert serialized_data["draft_url"] == website.get_full_url("draft")
    assert serialized_data["has_unpublished_live"] == website.has_unpublished_live
    assert serialized_data["has_unpublished_draft"] == website.has_unpublished_draft
    assert serialized_data["gdrive_url"] == (
        f"https://drive.google.com/drive/folders/abc123/{website.gdrive_folder}"
        if drive_credentials is not None and drive_folder is not None
        else None
    )
    assert serialized_data["url_path"] == website.url_path
    assert serialized_data["url_suggestion"] == website.url_path


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


def test_website_detail_serializer_with_url_format(mocker, ocw_site):
    """The url suggestion should be equal to the starter config site-url-format"""
    user = UserFactory.create(is_superuser=True)
    serialized = WebsiteDetailSerializer(
        instance=ocw_site,
        context={"request": mocker.Mock(user=user)},
    ).data
    assert serialized["url_path"] is None
    assert (
        serialized["url_suggestion"]
        == SiteConfig(ocw_site.starter.config).site_url_format
    )


def test_website_detail_serializer_with_url_format_partial(mocker, ocw_site):
    """The url suggestion should have relevant metadata fields filled in"""
    user = UserFactory.create(is_superuser=True)
    term = "Fall"
    year = "2028"
    content = ocw_site.websitecontent_set.get(type=CONTENT_TYPE_METADATA)
    content.metadata["term"] = term
    content.metadata["year"] = year
    content.save()
    expected_suggestion = (
        SiteConfig(ocw_site.starter.config)
        .site_url_format.replace("[sitemetadata:term]", term.lower())
        .replace("[sitemetadata:year]", year)
    )
    serialized = WebsiteDetailSerializer(
        instance=ocw_site,
        context={"request": mocker.Mock(user=user)},
    ).data
    assert serialized["url_path"] is None
    assert serialized["url_suggestion"] == expected_suggestion


def test_website_collaborator_serializer():
    """WebsiteCollaboratorSerializer should serialize a User object with correct fields"""
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
    assert serialized_data["website_name"] == content.website.name
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["updated_on"] == content.updated_on.isoformat()[:-6] + "Z"
    assert "markdown" not in serialized_data
    assert "metadata" not in serialized_data


def test_website_content_detail_serializer():
    """WebsiteContentDetailSerializer should serialize all relevant fields to the frontend"""
    content = WebsiteContentFactory.create(
        website=WebsiteFactory.create(url_path="courses/mysite-fall-2022")
    )
    serialized_data = WebsiteContentDetailSerializer(instance=content).data
    assert serialized_data["text_id"] == str(content.text_id)
    assert serialized_data["title"] == content.title
    assert serialized_data["type"] == content.type
    assert serialized_data["updated_on"] == content.updated_on.isoformat()[:-6] + "Z"
    assert serialized_data["markdown"] == content.markdown
    assert serialized_data["metadata"] == content.metadata
    assert serialized_data["url_path"] == content.website.url_path


def test_website_content_detail_serializer_with_url_format():
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
    settings.OCW_COURSE_STARTER_SLUG = "course"
    starter = WebsiteStarter.objects.get(slug=settings.OCW_COURSE_STARTER_SLUG)
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
def test_website_content_detail_serializer_content_context(  # pylint:disable=too-many-arguments,too-many-locals  # noqa: PLR0913
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
                    "fields": (
                        [{"name": "outer", "fields": field_list}]
                        if nested
                        else field_list
                    )
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


def test_website_content_detail_serializer_save(mocker, mocked_website_funcs):
    """WebsiteContentDetailSerializer should modify only certain fields"""
    content = WebsiteContentFactory.create(
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "to_keep": "old value 1",
            "to_update": "old value 2",
        },
    )
    existing_text_id = content.text_id
    new_title = f"{content.title} with some more text"
    new_type = f"{content.type}_other"
    new_markdown = "hopefully different from the previous markdown"
    metadata_patch = {"to_update": "updated value 2", "created": "brand new!"}
    user = UserFactory.create()
    # uuid value is invalid but it's ignored since it's marked readonly
    serializer = WebsiteContentDetailSerializer(
        data={
            "title": new_title,
            "text_id": "----",
            "type": new_type,
            "markdown": new_markdown,
            "metadata": metadata_patch,
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
    assert content.metadata == {
        "to_keep": "old value 1",
        "to_update": "updated value 2",
        "created": "brand new!",
    }
    assert content.updated_by == user
    mocked_website_funcs.update_website_backend.assert_called_once_with(content.website)


@pytest.mark.parametrize("is_new", [True])
@pytest.mark.parametrize("has_title_field", [True, False])
def test_website_content_detail_serializer_save_site_meta(  # pylint:disable=unused-argument
    settings, mocker, mocked_website_funcs, has_title_field, is_new
):
    """Website title should be updated if the expected title field is in metadata"""
    settings.FIELD_METADATA_TITLE = "course_title"
    new_title = "Updated Site Title"
    title_field = settings.FIELD_METADATA_TITLE if has_title_field else "other_title"
    if is_new:
        website = WebsiteFactory.create()
        instance_kwargs = {}
        serializer_class = WebsiteContentCreateSerializer
    else:
        content = WebsiteContentFactory.create(
            type=CONTENT_TYPE_METADATA,
            metadata={},
        )
        website = content.website
        instance_kwargs = {"instance": content}
        serializer_class = WebsiteContentDetailSerializer
    assert website.title != new_title
    serializer = serializer_class(
        data={
            "type": CONTENT_TYPE_METADATA,
            "website_id": website.pk,
            "metadata": {title_field: new_title},
        },
        context={
            "view": mocker.Mock(kwargs={"parent_lookup_website": website.name}),
            "request": mocker.Mock(user=UserFactory.create()),
            "website_id": website.pk,
        },
        **instance_kwargs,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    website.refresh_from_db()
    assert (website.title == new_title) is has_title_field


def test_website_content_detail_serializer_save_null_metadata(
    mocker, mocked_website_funcs
):
    """WebsiteContentDetailSerializer should save if metadata is null"""
    content = WebsiteContentFactory.create(
        type=CONTENT_TYPE_RESOURCE,
        metadata=None,
    )
    existing_text_id = content.text_id
    new_markdown = "hopefully this saves without error"
    metadata_patch = {"meta": "data"}
    user = UserFactory.create()
    # uuid value is invalid but it's ignored since it's marked readonly
    serializer = WebsiteContentDetailSerializer(
        data={
            "text_id": "----",
            "markdown": new_markdown,
            "metadata": metadata_patch,
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
    assert content.text_id == existing_text_id
    assert content.markdown == new_markdown
    assert content.metadata == {"meta": "data"}
    assert content.updated_by == user
    mocked_website_funcs.update_website_backend.assert_called_once_with(content.website)


@pytest.mark.parametrize("add_context_data", [True, False])
def test_website_content_create_serializer(
    mocker, mocked_website_funcs, add_context_data
):
    """
    WebsiteContentCreateSerializer should create a new WebsiteContent object, using context data as an override
    if extra context data is passed in.
    """
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
    mocked_website_funcs.update_website_backend.assert_called_once_with(content.website)
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
    """The WebsitePublishSerializer should return the correct base_url value"""
    site = WebsiteFactory.create(url_path="courses/my-site")
    settings.ROOT_WEBSITE_NAME = site.name if is_root_site else "some_other_root_name"
    serializer = WebsiteMassBuildSerializer(site)
    assert serializer.data["base_url"] == ("" if is_root_site else site.url_path)


@pytest.mark.parametrize("has_metadata", [True, False])
@pytest.mark.parametrize("has_legacy_uid", [True, False])
def test_website_unpublish_serializer(has_legacy_uid, has_metadata):
    """The WebsiteUnublishSerializer should return the correct value for site_uid"""
    site = WebsiteFactory.create(unpublished=True)
    legacy_uid = "e6748-d7d8-76a46-5cbc-5a42-12d3619e09"
    if has_metadata:
        WebsiteContentFactory.create(
            website=site,
            type=CONTENT_TYPE_METADATA,
            metadata=({"legacy_uid": legacy_uid} if has_legacy_uid else {}),
        )
    serializer = WebsiteUnpublishSerializer(site)
    assert serializer.data["site_uid"] == (
        legacy_uid.replace("-", "")
        if has_legacy_uid and has_metadata
        else site.uuid.hex
    )


def test_website_url_serializer_update(ocw_site, parsed_site_config):
    """WebsiteUrlSerializer should update the website url_path"""
    new_url_path = "1.45-test-course-fall-2012"
    data = {"url_path": new_url_path}
    serializer = WebsiteUrlSerializer(ocw_site, data)
    assert serializer.is_valid()
    assert serializer.validated_data["url_path"] == new_url_path
    serializer.update(ocw_site, serializer.validated_data)
    ocw_site.refresh_from_db()
    assert (
        ocw_site.url_path
        == f"{parsed_site_config[WEBSITE_CONFIG_ROOT_URL_PATH_KEY]}/{new_url_path}"
    )


def test_website_url_serializer_incomplete_url_path(ocw_site):
    """WebsiteUrlSerializer should invalidate a url_path that still has brackets"""
    new_url_path = "1.45-test-course-[metadata.semester]-2012"
    data = {"url_path": new_url_path}
    serializer = WebsiteUrlSerializer(ocw_site, data)
    assert serializer.is_valid() is False
    assert serializer.errors.get("url_path") == [
        "You must replace the url sections in brackets"
    ]


def test_website_url_serializer_duplicate_url_path(ocw_site, parsed_site_config):
    """WebsiteUrlSerializer should invalidate a duplicate url_path"""
    new_url_path = "1.45-test-course-spring-2022"
    WebsiteFactory.create(
        url_path=f"{parsed_site_config[WEBSITE_CONFIG_ROOT_URL_PATH_KEY]}/{new_url_path}"
    )
    data = {"url_path": new_url_path}
    serializer = WebsiteUrlSerializer(ocw_site, data)
    assert serializer.is_valid() is False
    assert serializer.errors.get("url_path") == [
        "The given website URL is already in use."
    ]


def test_website_url_serializer_url_path_published(ocw_site):
    """WebsiteUrlSerializer should invalidate a url_path for a published site"""
    ocw_site.publish_date = now_in_utc()
    new_url_path = "1.45-test-course-spring-2022"
    data = {"url_path": new_url_path}
    serializer = WebsiteUrlSerializer(ocw_site, data)
    assert serializer.is_valid() is False
    assert serializer.errors.get("url_path") == [
        "The URL cannot be changed after publishing."
    ]


def test_website_export_serializer(ocw_site):
    """ExportWebsiteSerializer should strip out user and publishing information"""
    user = UserFactory.create()
    now = now_in_utc()
    ocw_site.owner = user
    ocw_site.updated_by = user
    ocw_site.has_unpublished_draft = False
    ocw_site.draft_publish_date = now
    ocw_site.latest_build_id_draft = 1
    ocw_site.draft_publish_status = PUBLISH_STATUS_SUCCEEDED
    ocw_site.draft_publish_status_updated_on = now
    ocw_site.draft_last_published_by = user
    ocw_site.has_unpublished_live = False
    ocw_site.live_publish_date = now
    ocw_site.latest_build_id_live = 1
    ocw_site.live_publish_status = PUBLISH_STATUS_SUCCEEDED
    ocw_site.live_publish_status_updated_on = now
    ocw_site.live_last_published_by = user
    ocw_site.unpublish_status = PUBLISH_STATUS_NOT_STARTED
    ocw_site.unpublish_status_updated_on = now
    ocw_site.last_unpublished_by = user
    serializer = ExportWebsiteSerializer(ocw_site)
    data = serializer.data
    assert data["fields"]["owner"] is None
    assert data["fields"]["has_unpublished_draft"] is True
    assert data["fields"]["draft_publish_date"] is None
    assert data["fields"]["latest_build_id_draft"] is None
    assert data["fields"]["draft_publish_status"] == PUBLISH_STATUS_NOT_STARTED
    assert data["fields"]["draft_publish_status_updated_on"] is None
    assert data["fields"]["draft_last_published_by"] is None
    assert data["fields"]["has_unpublished_live"] is True
    assert data["fields"]["publish_date"] is None
    assert data["fields"]["latest_build_id_live"] is None
    assert data["fields"]["live_publish_status"] == PUBLISH_STATUS_NOT_STARTED
    assert data["fields"]["live_publish_status_updated_on"] is None
    assert data["fields"]["live_last_published_by"] is None
    assert data["fields"]["unpublish_status"] is None
    assert data["fields"]["unpublish_status_updated_on"] is None
    assert data["fields"]["last_unpublished_by"] is None


def test_website_content_export_serializer(ocw_site):
    """ExportWebsiteSerializer should strip out user information"""
    user = UserFactory.create()
    content = WebsiteContentFactory.create(
        owner=user, updated_by=user, file="http://example.com/file.txt"
    )
    serializer = ExportWebsiteContentSerializer(content)
    data = serializer.data
    assert data["fields"]["owner"] is None
    assert data["fields"]["updated_by"] is None
    assert data["fields"]["file"] == str(Path(content.website.url_path) / "file.txt")
