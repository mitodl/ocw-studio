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
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import Website, WebsiteContent
from websites.serializers import (
    WebsiteContentDetailSerializer,
    WebsiteDetailSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
)


# pylint:disable=redefined-outer-name,too-many-arguments

pytestmark = pytest.mark.django_db


@pytest.fixture
def websites(course_starter):
    """ Create some websites for tests """
    courses = WebsiteFactory.create_batch(3, published=True, starter=course_starter)
    noncourses = WebsiteFactory.create_batch(2, published=True)
    WebsiteFactory.create(unpublished=True, starter=course_starter)
    WebsiteFactory.create(future_publish=True)
    return SimpleNamespace(courses=courses, noncourses=noncourses)


@pytest.fixture
def file_upload():
    """File upload for tests"""
    return SimpleUploadedFile("exam.pdf", b"sample pdf", content_type="application/pdf")


@pytest.mark.parametrize("website_type", [constants.COURSE_STARTER_SLUG, None])
def test_websites_endpoint_list(drf_client, website_type, websites):
    """Test new websites endpoint for lists"""
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
            constants.COURSE_STARTER_SLUG if filter_by_type else site.starter.slug
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
                "starter": starter.id,
            },
        )
        assert resp.status_code == (201 if has_perm else 403)
        if has_perm:
            website = Website.objects.get(name=f"{user.username}_site")
            assert website.owner == user
            mock_create_website_backend.assert_any_call(website)


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
        side_effect=[GithubException(status=422, data={})],
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
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-publish", kwargs={"name": website.name})
    )
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
        side_effect=[GithubException(status=422, data={})],
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


def test_websites_endpoint_sorting(drf_client, websites):
    """ Response should be sorted according to query parameter """
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    resp = drf_client.get(
        reverse("websites_api-list"),
        {"sort": "title", "type": constants.COURSE_STARTER_SLUG},
    )
    for idx, course in enumerate(sorted(websites.courses, key=lambda site: site.title)):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)


def test_websites_autogenerate_name(drf_client):
    """ Website POST endpoint should auto-generate a name if one is not supplied """
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    website_title = "My Title"
    slugified_title = slugify(website_title)
    resp = drf_client.post(
        reverse("websites_api-list"),
        {"title": website_title, "starter": starter.id},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["name"] == slugified_title


def test_website_starters_list(drf_client, course_starter):
    """ Website starters endpoint should return a serialized list """
    new_starter = WebsiteStarterFactory.create(source=constants.STARTER_SOURCE_GITHUB)
    resp = drf_client.get(reverse("website_starters_api-list"))
    serialized_data = WebsiteStarterSerializer(
        [course_starter, new_starter], many=True
    ).data
    assert len(resp.data) == 2
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


@pytest.mark.parametrize("use_local_starters,exp_result_count", [[True, 3], [False, 2]])
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


@pytest.mark.parametrize("filter_type", ["page", ""])
def test_websites_content_list(drf_client, filter_type, permission_groups):
    """The list view of WebsiteContent should optionally filter by type"""
    drf_client.force_login(permission_groups.global_admin)
    WebsiteContentFactory.create()  # a different website, shouldn't show up here
    content = WebsiteContentFactory.create(type="other")
    website = content.website
    num_results = 5
    contents = [
        WebsiteContentFactory.create(type="page", website=website)
        for _ in range(num_results)
    ]
    WebsiteContentFactory.create(
        type="page", website=website
    ).delete()  # soft-deleted content shouldn't show up
    if not filter_type:
        contents += [content]
    resp = drf_client.get(
        reverse(
            "websites_content_api-list",
            kwargs={
                "parent_lookup_website": website.name,
            },
        ),
        {"type": filter_type},
    )
    results = resp.data["results"]
    assert resp.data["count"] == (num_results if filter_type else num_results + 1)
    assert len(results) == (num_results if filter_type else num_results + 1)

    for idx, content in enumerate(
        reversed(sorted(contents, key=lambda _content: _content.updated_on))
    ):
        assert content.title == results[idx]["title"]
        assert str(content.text_id) == results[idx]["text_id"]
        assert content.type == results[idx]["type"]


def test_websites_content_detail(drf_client, permission_groups):
    """The detail view for WebsiteContent should return serialized data"""
    drf_client.force_login(permission_groups.global_admin)
    content = WebsiteContentFactory.create(type="other")
    resp = drf_client.get(
        reverse(
            "websites_content_api-detail",
            kwargs={
                "parent_lookup_website": content.website.name,
                "text_id": str(content.text_id),
            },
        )
    )
    assert resp.data == WebsiteContentDetailSerializer(instance=content).data


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


def test_websites_content_create(drf_client, permission_groups):
    """POSTing to the WebsiteContent list view should create a new WebsiteContent"""
    drf_client.force_login(permission_groups.global_admin)
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


def test_websites_content_create_with_upload(
    drf_client, permission_groups, file_upload
):
    """Uploading a file when creating a new WebsiteContent object should work"""
    drf_client.force_login(permission_groups.global_admin)
    website = WebsiteFactory.create()
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
    assert (
        content.file.name
        == f"{website.name}/{content.text_id.replace('-', '')}_{file_upload.name}"
    )
    assert content.type == payload["type"]
    assert resp.data["text_id"] == str(content.text_id)


def test_websites_content_edit_with_upload(drf_client, permission_groups, file_upload):
    """Uploading a file when editing a new WebsiteContent object should work"""
    drf_client.force_login(permission_groups.global_admin)
    content = WebsiteContentFactory.create(type=constants.CONTENT_TYPE_RESOURCE)
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
        == f"{content.website.name}/{content.text_id.replace('-', '')}_{file_upload.name}"
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
    permission_groups,
    has_matching_config_item,
    is_page_content,
    exp_page_content_field,
):
    """
    POSTing to the WebsiteContent list view with a page content object should create a WebsiteContent record with
    a field that indicates that it's page content
    """
    drf_client.force_login(permission_groups.global_admin)
    found_config_item = mocker.Mock() if has_matching_config_item else None
    patched_find_config_item = mocker.patch(
        "websites.views.find_config_item", return_value=found_config_item
    )
    patched_is_page_content = mocker.patch(
        "websites.views.is_page_content", return_value=is_page_content
    )
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
    assert content.is_page_content == exp_page_content_field
    patched_find_config_item.assert_called_once()
    # Only check if the config item is for page content if that config item was actually found
    assert patched_is_page_content.call_count == (
        1 if found_config_item is not None else 0
    )


def test_websites_content_create_empty(drf_client, permission_groups):
    """POSTing to the WebsiteContent list view should create a new WebsiteContent"""
    drf_client.force_login(permission_groups.global_admin)
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
