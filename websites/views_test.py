""" Tests for websites views """
from types import SimpleNamespace

import factory
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.text import slugify
from github import GithubException
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status

from main import features
from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from websites import constants
from websites.factories import (
    WebsiteCollectionFactory,
    WebsiteCollectionItemFactory,
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.messages import PreviewOrPublishSuccessMessage
from websites.models import (
    Website,
    WebsiteCollection,
    WebsiteCollectionItem,
    WebsiteContent,
)
from websites.serializers import (
    WebsiteCollectionItemSerializer,
    WebsiteContentDetailSerializer,
    WebsiteDetailSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
)


# pylint:disable=redefined-outer-name,too-many-arguments,too-many-lines

pytestmark = pytest.mark.django_db

MOCK_GITHUB_DATA = {
    "before": "abc123",
    "after": "def456",
    "repository": {
        "html_url": "https:github.com/ocw-org/ocw-configs",
    },
    "commits": [
        {"modified": ["site-1/ocw-studio.yaml", "site-1/config.yaml"], "added": []},
        {"added": ["site-2/ocw-studio.yaml", "site-2/config.yaml"], "modified": []},
    ],
}


@pytest.fixture
def websites(course_starter):
    """ Create some websites for tests """
    courses = WebsiteFactory.create_batch(3, published=True, starter=course_starter)
    noncourses = WebsiteFactory.create_batch(2, published=True)
    WebsiteFactory.create(published=True, starter=course_starter, metadata=None)
    WebsiteFactory.create(unpublished=True, starter=course_starter)
    WebsiteFactory.create(future_publish=True)
    return SimpleNamespace(courses=courses, noncourses=noncourses)


@pytest.fixture
def file_upload():
    """File upload for tests"""
    return SimpleUploadedFile("exam.pdf", b"sample pdf", content_type="application/pdf")


@pytest.mark.parametrize("filter_by_type", [True, False])
def test_websites_endpoint_list(drf_client, filter_by_type, websites, settings):
    """Test new websites endpoint for lists"""
    website_type = settings.OCW_IMPORT_STARTER_SLUG if filter_by_type else None
    filter_by_type = website_type is not None
    now = now_in_utc()

    expected_websites = websites.courses
    if filter_by_type:
        resp = drf_client.get(reverse("websites_api-list"), {"type": website_type})
        assert resp.data.get("count") == 3
    else:
        expected_websites.extend(websites.noncourses)
        resp = drf_client.get(reverse("websites_api-list"))
        assert resp.data.get("count") == 5
    for idx, site in enumerate(
        sorted(expected_websites, reverse=True, key=lambda site: site.publish_date)
    ):
        assert resp.data.get("results")[idx]["uuid"] == str(site.uuid)
        assert resp.data.get("results")[idx]["starter"]["slug"] == (
            settings.OCW_IMPORT_STARTER_SLUG if filter_by_type else site.starter.slug
        )
        assert resp.data.get("results")[idx]["publish_date"] <= now.strftime(
            ISO_8601_FORMAT
        )


def test_websites_endpoint_list_permissions(drf_client, permission_groups):
    """Authenticated users should only see the websites they have permissions for"""
    for [user, count] in [
        [permission_groups.global_admin, 2],
        [permission_groups.global_author, 0],
        [permission_groups.site_admin, 1],
        [permission_groups.websites[0].owner, 2],
    ]:
        drf_client.force_login(user)
        resp = drf_client.get(reverse("websites_api-list"))
        assert resp.data.get("count") == count
        if count == 1:
            assert (
                resp.data.get("results")[0]["name"]
                == permission_groups.websites[0].name
            )
        if count == 2:
            assert (
                resp.data.get("results")[0]["updated_on"]
                >= resp.data.get("results")[1]["updated_on"]
            )


def test_websites_endpoint_list_create(mocker, drf_client, permission_groups):
    """
    Only global admins and authors should be able to send a POST request
    WebsiteContentCreateSerializer should create a new WebsiteContent, with some validation
    """
    mock_create_website_backend = mocker.patch(
        "websites.serializers.create_website_backend"
    )
    mock_create_website_pipeline = mocker.patch(
        "websites.serializers.create_website_publishing_pipeline"
    )
    starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    for [user, has_perm] in [
        [permission_groups.global_admin, True],
        [permission_groups.global_author, True],
        [permission_groups.site_admin, False],
        [permission_groups.websites[0].owner, False],
    ]:
        drf_client.force_login(user)
        resp = drf_client.post(
            reverse("websites_api-list"),
            data={
                "name": f"{user.username}_site",
                "title": "Fake",
                "short_id": f"test-id-{user.id}",
                "starter": starter.id,
            },
        )
        assert resp.status_code == (201 if has_perm else 403)
        if has_perm:
            website = Website.objects.get(name=f"{user.username}_site")
            assert website.owner == user
            mock_create_website_backend.assert_any_call(website)
            mock_create_website_pipeline.assert_any_call(website)


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_websites_endpoint_list_forbidden_methods(drf_client, method):
    """No put, patch, or delete requests allowed at this endpoint"""
    drf_client.force_login(UserFactory.create(is_superuser=True))
    client_func = getattr(drf_client, method)
    resp = client_func(
        reverse("websites_api-list"), data={"name": "fakename", "title": "Fake Title"}
    )
    assert resp.status_code == 405


@pytest.mark.parametrize("is_admin", [True, False])
def test_websites_endpoint_detail(drf_client, is_admin, permission_groups):
    """Test new websites endpoint for details"""
    website = permission_groups.websites[0]
    drf_client.force_login(website.owner if is_admin else permission_groups.site_editor)
    resp = drf_client.get(reverse("websites_api-detail", kwargs={"name": website.name}))
    response_data = resp.json()
    serialized_data = WebsiteDetailSerializer(instance=website).data
    assert response_data["is_admin"] == is_admin
    response_data.pop("is_admin")
    serialized_data.pop("is_admin")
    assert response_data == serialized_data


@pytest.mark.parametrize(
    "method,status", [["post", 405], ["put", 403], ["delete", 405]]
)
def test_websites_endpoint_detail_methods_denied(drf_client, method, status):
    """Certain request methods should always be denied"""
    website = WebsiteFactory.create()
    drf_client.force_login(UserFactory.create(is_superuser=True))
    client_func = getattr(drf_client, method)
    resp = client_func(reverse("websites_api-detail", kwargs={"name": website.name}))
    assert resp.status_code == status


def test_websites_endpoint_detail_update(mocker, drf_client):
    """A user with admin permissions should be able to edit a website but not change website owner"""
    mock_update_website_backend = mocker.patch(
        "websites.serializers.update_website_backend"
    )
    mock_create_website_pipeline = mocker.patch(
        "websites.serializers.create_website_publishing_pipeline"
    )
    website = WebsiteFactory.create()
    admin_user = UserFactory.create()
    admin_user.groups.add(website.admin_group)
    drf_client.force_login(admin_user)
    new_title = "New Title"
    resp = drf_client.patch(
        reverse("websites_api-detail", kwargs={"name": website.name}),
        data={"title": new_title, "owner": admin_user.id},
    )
    assert resp.status_code == 200
    updated_site = Website.objects.get(name=website.name)
    assert updated_site.title == new_title
    assert updated_site.owner == website.owner
    mock_update_website_backend.assert_called_once_with(website)
    mock_create_website_pipeline.assert_not_called()


def test_websites_endpoint_preview(mocker, drf_client):
    """A user with admin/edit permissions should be able to request a website preview"""
    mock_preview_website = mocker.patch("websites.views.preview_website")
    website = WebsiteFactory.create()
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.post(
        reverse("websites_api-preview", kwargs={"name": website.name})
    )
    assert resp.status_code == 200
    mock_preview_website.assert_called_once_with(website)


def test_websites_endpoint_preview_error(mocker, drf_client):
    """ An exception raised by the api preview call should be handled gracefully """
    mocker.patch(
        "websites.views.preview_website",
        side_effect=[GithubException(status=422, data={}, headers={})],
    )
    website = WebsiteFactory.create()
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.post(
        reverse("websites_api-preview", kwargs={"name": website.name})
    )
    assert resp.status_code == 500
    assert resp.data == {"details": "422 {}"}


def test_websites_endpoint_publish(mocker, drf_client):
    """A user with admin permissions should be able to request a website publish"""
    mock_publish_website = mocker.patch("websites.views.publish_website")
    website = WebsiteFactory.create()
    last_published = website.publish_date
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-publish", kwargs={"name": website.name})
    )
    website.refresh_from_db()
    assert website.publish_date > last_published
    assert resp.status_code == 200
    mock_publish_website.assert_called_once_with(website)


def test_websites_endpoint_publish_denied(mocker, drf_client):
    """A user with edit permissions should not be able to request a website publish"""
    mocker.patch("websites.views.publish_website")
    website = WebsiteFactory.create()
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.post(
        reverse("websites_api-publish", kwargs={"name": website.name})
    )
    assert resp.status_code == 500
    assert resp.data == {
        "details": "You do not have permission to perform this action."
    }


def test_websites_endpoint_publish_error(mocker, drf_client):
    """ An exception raised by the api publish call should be handled gracefully """
    mocker.patch(
        "websites.views.publish_website",
        side_effect=[GithubException(status=422, data={}, headers={})],
    )
    website = WebsiteFactory.create()
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-publish", kwargs={"name": website.name})
    )
    assert resp.status_code == 500
    assert resp.data == {"details": "422 {}"}


@pytest.mark.parametrize("version", ["live", "draft"])
def test_websites_endpoint_pipeline_complete(
    settings, mocker, drf_client, permission_groups, version
):
    """The pipeline_complete endpoint should send notifications to site owner/admins"""
    settings.OCW_STUDIO_LIVE_URL = "http://test.live.edu/"
    settings.OCW_STUDIO_DRAFT_URL = "http://test.draft.edu"
    mock_get_message_sender = mocker.patch("websites.views.get_message_sender")
    mock_sender = mock_get_message_sender.return_value.__enter__.return_value
    settings.API_BEARER_TOKEN = "abc123"
    website = permission_groups.websites[0]
    drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.API_BEARER_TOKEN}")
    resp = drf_client.post(
        reverse("websites_api-pipeline-complete", kwargs={"name": website.name}),
        data={"version": version, "success": True},
    )
    mock_get_message_sender.assert_called_once_with(PreviewOrPublishSuccessMessage)
    assert mock_sender.build_and_send_message.call_count == 2
    for user in [website.owner]:
        mock_sender.build_and_send_message.assert_any_call(
            user,
            {
                "site": {
                    "title": website.title,
                    "url": f"http://test.{version}.edu/{website.starter.config['root-url-path']}/{website.name}",
                },
                "version": version,
            },
        )
    assert resp.status_code == 200


@pytest.mark.parametrize("token", ["abc123", None])
def test_websites_endpoint_pipeline_complete_denied(
    settings, drf_client, permission_groups, token
):
    """The pipeline_complete endpoint should raise a permission error without a valid token"""
    settings.API_BEARER_TOKEN = token
    website = permission_groups.websites[0]
    drf_client.credentials(HTTP_AUTHORIZATION="Bearer wrong-token")
    resp = drf_client.post(
        reverse("websites_api-pipeline-complete", kwargs={"name": website.name}),
        json={"version": "live", "success": True},
    )
    assert resp.status_code == 403


def test_websites_endpoint_detail_update_denied(drf_client):
    """A user with editor permissions should be able to view but not edit a website"""
    website = WebsiteFactory.create()
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.get(reverse("websites_api-detail", kwargs={"name": website.name}))
    assert resp.status_code == 200
    resp = drf_client.patch(
        reverse("websites_api-detail", kwargs={"name": website.name}),
        data={"title": "New"},
    )
    assert resp.status_code == 403


def test_websites_endpoint_detail_get_denied(drf_client):
    """Anonymous user or user without permissions should not be able to view the site"""
    for user in (None, UserFactory.create()):
        if user:
            drf_client.force_login(user)
        website = WebsiteFactory.create()
        resp = drf_client.get(
            reverse("websites_api-detail", kwargs={"name": website.name})
        )
        assert resp.status_code == 403 if not user else 404


def test_websites_endpoint_sorting(drf_client, websites, settings):
    """ Response should be sorted according to query parameter """
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    resp = drf_client.get(
        reverse("websites_api-list"),
        {"sort": "title", "type": settings.OCW_IMPORT_STARTER_SLUG},
    )
    for idx, course in enumerate(sorted(websites.courses, key=lambda site: site.title)):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)


def test_website_endpoint_search(drf_client):
    """ should limit the queryset based on the search param """
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)

    WebsiteFactory.create(title="BEST")
    WebsiteFactory.create(title="WORST")
    resp = drf_client.get(reverse("websites_api-list"), {"search": "BEST"})
    assert [website["title"] for website in resp.data.get("results")] == ["BEST"]


def test_websites_autogenerate_name(mocker, drf_client):
    """ Website POST endpoint should auto-generate a name if one is not supplied """
    mock_create_website_pipeline = mocker.patch(
        "websites.serializers.create_website_publishing_pipeline"
    )
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    website_title = "My Title"
    website_short_id = "my-title"
    slugified_title = slugify(website_title)
    resp = drf_client.post(
        reverse("websites_api-list"),
        {"title": website_title, "short_id": website_short_id, "starter": starter.id},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["name"] == slugified_title
    assert resp.data["short_id"] == website_short_id
    mock_create_website_pipeline.assert_called_once()


def test_website_starters_list(settings, drf_client, course_starter):
    """ Website starters endpoint should return a serialized list """
    settings.FEATURES[features.USE_LOCAL_STARTERS] = False
    new_starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    resp = drf_client.get(reverse("website_starters_api-list"))
    expected_starters = [course_starter, new_starter]
    serialized_data = WebsiteStarterSerializer(expected_starters, many=True).data
    assert len(resp.data) == len(expected_starters)
    assert sorted(resp.data, key=lambda _starter: _starter["id"]) == sorted(
        serialized_data, key=lambda _starter: _starter["id"]
    )


def test_website_starters_retrieve(drf_client):
    """ Website starters endpoint should return a single serialized starter """
    starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    resp = drf_client.get(
        reverse("website_starters_api-detail", kwargs={"pk": starter.id})
    )
    assert resp.json() == WebsiteStarterDetailSerializer(instance=starter).data


@pytest.mark.parametrize("use_local_starters,exp_result_count", [[True, 4], [False, 2]])
def test_website_starters_local(
    settings, drf_client, use_local_starters, exp_result_count
):
    """ Website starters endpoint should only return local starters if a feature flag is set to True """
    settings.FEATURES[features.USE_LOCAL_STARTERS] = use_local_starters
    WebsiteStarterFactory.create_batch(
        2,
        source=factory.Iterator(
            [constants.STARTER_SOURCE_LOCAL, constants.STARTER_SOURCE_GITHUB]
        ),
    )
    resp = drf_client.get(reverse("website_starters_api-list"))
    assert len(resp.data) == exp_result_count


def test_website_starters_site_configs_not_github(drf_client):
    """A 400 response should be returned if the request is not from github"""
    resp = drf_client.post(reverse("website_starters_api-site-configs"), data={})
    assert resp.status_code == 400


def test_website_starters_site_configs_invalid_key(drf_client):
    """A 403 response should be returned if the request signature is invalid"""
    drf_client.credentials(HTTP_X_HUB_SIGNATURE="dfdfdf=dkfldkfl")
    resp = drf_client.post(
        reverse("website_starters_api-site-configs"), data=MOCK_GITHUB_DATA
    )
    assert resp.status_code == 403


def test_website_starters_site_configs(settings, mocker, drf_client):
    """A 202 response should be returned for valid data"""
    settings.GIT_TOKEN = "git-token"
    mocker.patch("websites.views.valid_key", return_value=True)
    valid_config_files = ["site-1/ocw-studio.yaml", "site-2/ocw-studio.yaml"]
    mock_sync = mocker.patch("content_sync.api.tasks.sync_github_site_configs.delay")
    resp = drf_client.post(
        reverse("website_starters_api-site-configs"), data=MOCK_GITHUB_DATA
    )
    mock_sync.assert_called_once_with(
        MOCK_GITHUB_DATA["repository"]["html_url"],
        valid_config_files,
        commit=MOCK_GITHUB_DATA["after"],
    )
    assert resp.status_code == 202


def test_website_starters_site_configs_exception(mocker, drf_client):
    """A 500 response should be returned if an unhandled exception is raised"""
    mocker.patch("websites.views.valid_key", side_effect=[KeyError("Key not found")])
    resp = drf_client.post(
        reverse("website_starters_api-site-configs"), data=MOCK_GITHUB_DATA
    )
    assert resp.status_code == 500
    assert resp.data == {"details": "'Key not found'"}


@pytest.mark.parametrize("detailed_list", [True, False])
@pytest.mark.parametrize(
    "filter_type, search, expected_num_results",
    [
        ["page", "text3", 1],
        ["page", "", 5],
        ["", "text3", 1],
        ["", "", 6],
    ],
)
def test_websites_content_list(
    drf_client,
    filter_type,
    search,
    detailed_list,
    global_admin_user,
    expected_num_results,
):
    """The list view of WebsiteContent should optionally filter by type"""
    drf_client.force_login(global_admin_user)
    WebsiteContentFactory.create()  # a different website, shouldn't show up here
    content = WebsiteContentFactory.create(type="other")
    website = content.website
    contents = [
        WebsiteContentFactory.create(
            type="page",
            website=website,
            title=f"some TEXT{num} here for a case insensitive search",
        )
        for num in range(5)
    ]
    WebsiteContentFactory.create(
        type="page", website=website
    ).delete()  # soft-deleted content shouldn't show up

    if not filter_type:
        contents += [content]
    query_params = {}
    if filter_type:
        query_params["type"] = filter_type
    if detailed_list:
        query_params["detailed_list"] = detailed_list
    if search:
        query_params["search"] = search

    resp = drf_client.get(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        query_params,
    )
    results = resp.data["results"]
    assert resp.data["count"] == expected_num_results
    assert len(results) == expected_num_results

    if search:
        contents = [content for content in contents if search in content.title.lower()]
    for idx, content in enumerate(
        reversed(sorted(contents, key=lambda _content: _content.updated_on))
    ):
        assert content.title == results[idx]["title"]
        assert str(content.text_id) == results[idx]["text_id"]
        assert content.type == results[idx]["type"]
        if detailed_list:
            # metadata appears because the detail serializer was used
            assert content.metadata == results[idx]["metadata"]
        else:
            assert "metadata" not in results[idx]


def test_websites_content_list_multiple_type(drf_client, global_admin_user):
    """The list view of WebsiteContent should be able to filter by multiple type values"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        3,
        website=website,
        type=factory.Iterator(["page", "resource", "other"]),
    )
    api_url = reverse(
        "websites_content_api-list",
        kwargs={
            "parent_lookup_website": website.name,
        },
    )
    resp = drf_client.get(
        api_url,
        {"type[0]": "page", "type[1]": "resource"},
    )
    assert resp.data["count"] == 2
    results = resp.data["results"]
    assert {result["type"] for result in results} == {"page", "resource"}


def test_websites_content_list_page_content(drf_client, global_admin_user):
    """The list view of WebsiteContent should be able to filter by page content only"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        3,
        website=website,
        type=factory.Iterator(["type1", "type2", "type3"]),
        is_page_content=factory.Iterator([True, False, False]),
    )
    api_url = reverse(
        "websites_content_api-list",
        kwargs={
            "parent_lookup_website": website.name,
        },
    )
    resp = drf_client.get(
        api_url,
        {"page_content": True},
    )
    assert resp.data["count"] == 1
    results = resp.data["results"]
    assert results[0]["type"] == "type1"


@pytest.mark.parametrize("content_context", [True, False])
def test_websites_content_detail(drf_client, global_admin_user, content_context):
    """The detail view for WebsiteContent should return serialized data"""
    drf_client.force_login(global_admin_user)
    content = WebsiteContentFactory.create(type="other")
    url = reverse(
        "websites_content_api-detail",
        kwargs={
            "parent_lookup_website": content.website.name,
            "text_id": str(content.text_id),
        },
    )
    resp = drf_client.get(f"{url}?content_context={content_context}")
    assert (
        resp.data
        == WebsiteContentDetailSerializer(
            instance=content, context={"content_context": content_context}
        ).data
    )


def test_websites_content_delete(drf_client, permission_groups, mocker):
    """DELETEing a WebsiteContent should soft-delete the object"""
    update_website_backend_mock = mocker.patch("websites.views.update_website_backend")
    drf_client.force_login(permission_groups.global_admin)
    content = WebsiteContentFactory.create(updated_by=permission_groups.site_editor)
    resp = drf_client.delete(
        reverse(
            "websites_content_api-detail",
            kwargs={
                "parent_lookup_website": content.website.name,
                "text_id": str(content.text_id),
            },
        )
    )
    assert resp.data is None
    content.refresh_from_db()
    assert content.updated_by == permission_groups.global_admin
    assert content.deleted is not None
    update_website_backend_mock.assert_called_once_with(content.website)


def test_websites_content_create(drf_client, global_admin_user):
    """POSTing to the WebsiteContent list view should create a new WebsiteContent"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    payload = {
        "title": "new title",
        "markdown": "some markdown",
        "type": constants.CONTENT_TYPE_PAGE,
    }
    resp = drf_client.post(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        data=payload,
    )
    assert resp.status_code == 201
    content = website.websitecontent_set.get()
    assert content.title == payload["title"]
    assert content.markdown == payload["markdown"]
    assert content.type == payload["type"]
    assert resp.data["text_id"] == str(content.text_id)


@pytest.mark.parametrize(
    "root_url_path, expected_prefix",
    [
        ["", ""],
        ["/", ""],
        ["/test/sites/", "test/sites"],
    ],
)
def test_websites_content_create_with_upload(
    drf_client, global_admin_user, file_upload, root_url_path, expected_prefix
):
    """Uploading a file when creating a new WebsiteContent object should work"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    if root_url_path is not None:
        starter = website.starter
        starter.config["root-url-path"] = root_url_path
        starter.save()
    payload = {
        "title": "new title",
        "type": constants.CONTENT_TYPE_RESOURCE,
        "file": file_upload,
    }
    resp = drf_client.post(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        data=payload,
        format="multipart",
    )
    assert resp.status_code == 201
    content = website.websitecontent_set.get()
    assert content.title == payload["title"]
    assert content.file.name == "/".join(
        [
            part
            for part in [
                expected_prefix,
                f"{website.name}/{content.text_id.replace('-', '')}_{file_upload.name}",
            ]
            if part
        ]
    )
    assert content.type == payload["type"]
    assert resp.data["text_id"] == str(content.text_id)


def test_websites_content_edit_with_upload(drf_client, global_admin_user, file_upload):
    """Uploading a file when editing a new WebsiteContent object should work"""
    drf_client.force_login(global_admin_user)
    content = WebsiteContentFactory.create(
        type=constants.CONTENT_TYPE_RESOURCE, metadata={"title": "test"}
    )
    payload = {"file": file_upload, "title": "New Title"}
    resp = drf_client.patch(
        reverse(
            "websites_content_api-detail",
            kwargs={
                "parent_lookup_website": content.website.name,
                "text_id": str(content.text_id),
            },
        ),
        data=payload,
        format="multipart",
    )
    assert resp.status_code == 200
    content = WebsiteContent.objects.get(id=content.id)
    assert content.title == payload["title"]
    assert (
        content.file.name
        == f"sites/{content.website.name}/{content.text_id.replace('-', '')}_{file_upload.name}"
    )
    assert resp.data["text_id"] == str(content.text_id)


@pytest.mark.parametrize(
    "has_matching_config_item, is_page_content, exp_page_content_field",
    [
        [True, True, True],
        [False, True, False],
        [True, False, False],
    ],
)
def test_content_create_page_content(
    mocker,
    drf_client,
    global_admin_user,
    has_matching_config_item,
    is_page_content,
    exp_page_content_field,
):
    """
    POSTing to the WebsiteContent list view with a page content object should create a WebsiteContent record with
    a field that indicates that it's page content
    """
    drf_client.force_login(global_admin_user)
    found_config_item = mocker.Mock() if has_matching_config_item else None
    patched_site_config = mocker.patch("websites.views.SiteConfig", autospec=True)
    patched_site_config.return_value.find_item_by_name.return_value = found_config_item
    patched_site_config.return_value.is_page_content.return_value = is_page_content
    website = WebsiteFactory.create()
    payload = {
        "title": "new title",
        "markdown": "some markdown",
        "type": constants.CONTENT_TYPE_PAGE,
        "dirpath": "path/to",
        "filename": "myfile",
    }
    resp = drf_client.post(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        data=payload,
    )
    assert resp.status_code == 201
    content = website.websitecontent_set.get()
    assert content.is_page_content == exp_page_content_field
    patched_site_config.return_value.find_item_by_name.assert_called_once()
    # Only check if the config item is for page content if that config item was actually found
    assert patched_site_config.return_value.is_page_content.call_count == (
        1 if found_config_item is not None else 0
    )


def test_content_create_page_added_context(mocker, drf_client, global_admin_user):
    """
    POSTing to the WebsiteContent list view without a filename should add a generated filename if a filename was not
    included in the request data
    """
    patched_get_filename = mocker.patch(
        "websites.views.get_valid_new_filename", return_value="my-title-100"
    )
    drf_client.force_login(global_admin_user)
    title = "My Title"
    website = WebsiteFactory.create()
    payload = {
        "title": title,
        "markdown": "some markdown",
        "type": "blog",
    }
    # "folder" path for the config item with type="blog" in basic-site-config.yml
    expected_dirpath = "content/blog"
    expected_filename = "my-title-100"
    resp = drf_client.post(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        data=payload,
    )
    assert resp.status_code == 201
    patched_get_filename.assert_called_once_with(
        website_pk=website.pk, dirpath=expected_dirpath, filename_base="my-title"
    )
    content = website.websitecontent_set.order_by("-created_on").first()
    assert content.website == website
    assert content.filename == expected_filename
    # "folder" path for the config item with type="blog" in basic-site-config.yml
    assert content.dirpath == expected_dirpath
    assert content.is_page_content is True


def test_websites_content_create_empty(drf_client, global_admin_user):
    """POSTing to the WebsiteContent list view should create a new WebsiteContent"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    payload = {}
    resp = drf_client.post(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        data=payload,
    )
    assert resp.status_code == 400
    assert "This field is required" in resp.data["type"][0]


def test_website_collection_create(drf_client, global_admin_user):
    """Test that we can create a new collection"""
    drf_client.force_login(global_admin_user)
    payload = {
        "title": "My Amazing Collection of Websites",
        "description": "A mediocre website collection :/",
    }
    resp = drf_client.post(
        reverse(
            "website_collection_api-list",
        ),
        data=payload,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    collection = WebsiteCollection.objects.last()
    assert collection.title == payload["title"]
    assert collection.description == payload["description"]
    assert collection.owner == global_admin_user


def test_website_collection_update(drf_client, global_admin_user):
    """Test that we can update a collection"""
    collection = WebsiteCollectionFactory.create()
    drf_client.force_login(global_admin_user)
    payload = {
        "title": "My Amazing Edited Collection",
        "description": "A mediocre website collection :/",
    }
    resp = drf_client.patch(
        reverse("website_collection_api-detail", kwargs={"id": collection.id}),
        data=payload,
    )
    assert resp.status_code == status.HTTP_200_OK
    collection.refresh_from_db()
    assert collection.title == payload["title"]
    assert collection.description == payload["description"]


def test_website_collection_create_anon(drf_client):
    """test that anon is blocked"""
    payload = {
        "title": "My Amazing Collection of Websites",
        "description": "A mediocre website collection :/",
    }
    resp = drf_client.post(
        reverse(
            "website_collection_api-list",
        ),
        data=payload,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_website_collection_anonymous_get(drf_client):
    """that an anonymous user can GET info about a collection"""
    collection = WebsiteCollectionFactory.create()
    resp = drf_client.get(
        reverse("website_collection_api-detail", kwargs={"id": collection.id})
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "title": collection.title,
        "description": collection.description,
        "id": collection.id,
    }


def test_website_collection_anon_non_owner_delete(drf_client):
    """anons and non-admins can't delete!"""
    collection = WebsiteCollectionFactory.create()
    for user in (None, UserFactory.create()):
        if user:
            drf_client.force_login(user)
        resp = drf_client.delete(
            reverse("website_collection_api-detail", kwargs={"id": collection.id})
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_website_collection_delete(drf_client, global_admin_user):
    """admin should be able to delete"""
    collection = WebsiteCollectionFactory.create(owner=global_admin_user)
    drf_client.force_login(global_admin_user)
    resp = drf_client.delete(
        reverse("website_collection_api-detail", kwargs={"id": collection.id})
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_website_collection_item_add(drf_client, global_admin_user):
    """test that we can add an item to a website collection"""
    collection = WebsiteCollectionFactory.create()
    website = WebsiteFactory.create()
    drf_client.force_login(global_admin_user)

    payload = {"website": website.uuid}
    resp = drf_client.post(
        reverse(
            "website_collection_item_api-list",
            kwargs={
                "parent_lookup_collection": collection.id,
            },
        ),
        data=payload,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert (
        WebsiteCollectionItem.objects.filter(website_collection=collection).count() == 1
    )


def test_website_collection_item_delete_anon(drf_client):
    """anons and non-admins shouldn't be able to delete"""
    item = WebsiteCollectionItemFactory.create()
    for user in (None, UserFactory.create()):
        if user:
            drf_client.force_login(user)
        resp = drf_client.delete(
            reverse(
                "website_collection_item_api-detail",
                kwargs={
                    "parent_lookup_collection": item.website_collection.id,
                    "pk": item.id,
                },
            )
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_website_collection_item_delete_admin(drf_client, global_admin_user):
    """admin should be able to delete"""
    item = WebsiteCollectionItemFactory.create()
    drf_client.force_login(global_admin_user)
    resp = drf_client.delete(
        reverse(
            "website_collection_item_api-detail",
            kwargs={
                "parent_lookup_collection": item.website_collection.id,
                "pk": item.id,
            },
        )
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_website_collection_item_add_anon(drf_client):
    """test that anon is blocked"""
    collection = WebsiteCollectionFactory.create()
    website = WebsiteFactory.create()
    payload = {"website": website.uuid, "website_collection": collection.id}
    resp = drf_client.post(
        reverse(
            "website_collection_item_api-list",
            kwargs={
                "parent_lookup_collection": collection.id,
            },
        ),
        data=payload,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert (
        WebsiteCollectionItem.objects.filter(website_collection=collection).count() == 0
    )


def test_website_collection_item_reorder(drf_client, global_admin_user):
    """test that the logic for reordering items works correctly"""
    drf_client.force_login(global_admin_user)
    collection = WebsiteCollectionFactory.create()
    one = WebsiteCollectionItemFactory.create(website_collection=collection, position=0)
    two = WebsiteCollectionItemFactory.create(website_collection=collection, position=1)
    three = WebsiteCollectionItemFactory.create(
        website_collection=collection, position=2
    )
    four = WebsiteCollectionItemFactory.create(
        website_collection=collection, position=3
    )

    # move 'four' to the first position (index 0)
    resp = drf_client.patch(
        reverse(
            "website_collection_item_api-detail",
            kwargs={"parent_lookup_collection": collection.id, "pk": four.id},
        ),
        data={"position": 0},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert list(
        WebsiteCollectionItem.objects.filter(website_collection=collection).order_by(
            "position"
        )
    ) == [four, one, two, three]

    # move 'four' up to the third position (index 2)
    resp = drf_client.patch(
        reverse(
            "website_collection_item_api-detail",
            kwargs={"parent_lookup_collection": collection.id, "pk": four.id},
        ),
        data={"position": 2},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert list(
        WebsiteCollectionItem.objects.filter(website_collection=collection).order_by(
            "position"
        )
    ) == [one, two, four, three]


def test_website_collection_items_get(drf_client):
    """test that we can get items in a collection"""
    collection = WebsiteCollectionFactory.create()
    one = WebsiteCollectionItemFactory.create(website_collection=collection, position=0)
    two = WebsiteCollectionItemFactory.create(website_collection=collection, position=1)
    three = WebsiteCollectionItemFactory.create(
        website_collection=collection, position=2
    )
    four = WebsiteCollectionItemFactory.create(
        website_collection=collection, position=3
    )
    # creating this item to ensure that other items aren't
    # included in the response
    WebsiteCollectionItemFactory.create()

    # move 'four' to the first position (index 0)
    resp = drf_client.get(
        reverse(
            "website_collection_item_api-list",
            kwargs={"parent_lookup_collection": collection.id},
        ),
    )
    assert resp.status_code == status.HTTP_200_OK
    assert (
        resp.data
        == WebsiteCollectionItemSerializer([one, two, three, four], many=True).data
    )
