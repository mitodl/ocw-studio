"""Tests for websites views"""

import datetime
from types import SimpleNamespace

import factory
import pytest
import pytz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.text import slugify
from github import GithubException
from mitol.common.utils.datetime import now_in_utc
from requests import HTTPError
from rest_framework import status

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.models import ContentSyncState
from main import features
from main.constants import ISO_8601_FORMAT
from users.factories import UserFactory
from websites import constants
from websites.constants import (
    CONTENT_TYPE_METADATA,
    PUBLISH_STATUS_NOT_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
)
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
    WebsiteStatusSerializer,
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
    """Create some websites for tests, with all but one having a sitemetadata WebsiteContent object"""
    courses = WebsiteFactory.create_batch(3, published=True, starter=course_starter)
    noncourses = WebsiteFactory.create_batch(2, published=True)
    not_published = [
        WebsiteFactory.create(published=True, starter=course_starter, metadata=None),
        WebsiteFactory.create(unpublished=True, starter=course_starter),
        WebsiteFactory.create(not_published=True, starter=course_starter),
        WebsiteFactory.create(future_publish=True),
    ]
    for site in [*courses, *noncourses, *not_published]:
        if site.metadata:
            WebsiteContentFactory.create(website=site, type="sitemetadata")
    return SimpleNamespace(
        courses=courses, noncourses=noncourses, not_published=not_published
    )


@pytest.fixture
def file_upload():
    """File upload for tests"""
    return SimpleUploadedFile("exam.pdf", b"sample pdf", content_type="application/pdf")


@pytest.mark.parametrize("filter_by_type", [True, False])
def test_websites_endpoint_list(drf_client, filter_by_type, websites, settings):
    """Test new websites endpoint for lists"""
    website_type = settings.OCW_COURSE_STARTER_SLUG if filter_by_type else None
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
        sorted(
            expected_websites,
            reverse=True,
            key=lambda site: site.first_published_to_production,
        )
    ):
        assert resp.data.get("results")[idx]["uuid"] == str(site.uuid)
        assert resp.data.get("results")[idx]["starter"]["slug"] == (
            settings.OCW_COURSE_STARTER_SLUG if filter_by_type else site.starter.slug
        )
        assert resp.data.get("results")[idx][
            "first_published_to_production"
        ] <= now.strftime(ISO_8601_FORMAT)


def test_websites_endpoint_list_permissions(drf_client, permission_groups, settings):
    """Authenticated users should only see the websites they have permissions for"""
    settings.OCW_TEST_SITE_SLUGS = ["ocw-ci-test-course"]
    for [user, count] in [
        [permission_groups.global_admin, 2],
        [permission_groups.global_author, 0],
        [permission_groups.site_admin, 1],
        [permission_groups.websites[0].owner, 2],
        [permission_groups.superuser, 3],
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
    starter = WebsiteStarterFactory.create(
        source=constants.STARTER_SOURCE_GITHUB,
        status=constants.WebsiteStarterStatus.ACTIVE,
    )
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


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_websites_endpoint_list_forbidden_methods(drf_client, method):
    """No put, patch, or delete requests allowed at this endpoint"""
    drf_client.force_login(UserFactory.create(is_superuser=True))
    client_func = getattr(drf_client, method)
    resp = client_func(
        reverse("websites_api-list"), data={"name": "fakename", "title": "Fake Title"}
    )
    assert resp.status_code == 405


def test_delete_video_content_triggers_cleanup(mocker, drf_client, permission_groups):
    """Test video deletion workflow"""
    delete_related_captions_mock = mocker.patch(
        "websites.views.delete_related_captions_and_transcript"
    )
    delete_resource_mock = mocker.patch("websites.views.delete_resource")
    update_backend_mock = mocker.patch("websites.views.update_website_backend")

    video_content = WebsiteContentFactory.create(
        type=constants.CONTENT_TYPE_RESOURCE,
        metadata={"resourcetype": constants.RESOURCE_TYPE_VIDEO},
    )

    drf_client.force_login(permission_groups.global_admin)
    url = reverse(
        "websites_content_api-detail",
        kwargs={
            "parent_lookup_website": video_content.website.name,
            "text_id": str(video_content.text_id),
        },
    )

    resp = drf_client.delete(url)

    assert resp.status_code == 204
    delete_related_captions_mock.assert_called_once_with(video_content)
    delete_resource_mock.assert_called_once_with(video_content)
    update_backend_mock.assert_called_once_with(video_content.website)


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


def test_websites_endpoint_status(drf_client):
    """The status API should return a subset of info for the website"""
    website = WebsiteFactory.create()
    drf_client.force_login(website.owner)
    resp = drf_client.get(
        f"{reverse('websites_api-detail', kwargs={'name': website.name})}?only_status=true"
    )
    response_data = resp.json()
    serialized_data = WebsiteStatusSerializer(instance=website).data
    assert response_data == serialized_data


@pytest.mark.parametrize(
    ("method", "status"),
    [["post", 405], ["put", 403], ["delete", 405]],  # noqa: PT007
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
    mock_trigger_publish = mocker.patch("websites.views.trigger_publish")
    now = datetime.datetime(2020, 1, 1, tzinfo=pytz.utc)
    mocker.patch("websites.views.now_in_utc", return_value=now)
    website = WebsiteFactory.create(url_path="courses/mysite")
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.post(
        reverse("websites_api-preview", kwargs={"name": website.name})
    )
    assert resp.status_code == 200
    mock_trigger_publish.assert_called_once_with(website.name, VERSION_DRAFT)
    website.refresh_from_db()
    assert website.has_unpublished_draft is False
    assert website.draft_publish_status == constants.PUBLISH_STATUS_NOT_STARTED
    assert website.draft_publish_status_updated_on == now
    assert website.draft_last_published_by == editor
    assert website.latest_build_id_draft is None


def test_websites_endpoint_preview_error(mocker, drf_client):
    """An exception raised by the api preview call should be handled gracefully"""
    mocker.patch(
        "websites.views.trigger_publish",
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


@pytest.mark.parametrize("unpublish_status", [PUBLISH_STATUS_NOT_STARTED, None])
def test_websites_endpoint_publish(mocker, drf_client, unpublish_status):
    """
    A user with admin permissions should be able to request a website publish and revert
    any previous unpublish request
    """
    mock_publish_website = mocker.patch("websites.views.trigger_publish")
    now = datetime.datetime(2020, 1, 1, tzinfo=pytz.utc)
    mocker.patch("websites.views.now_in_utc", return_value=now)
    website = WebsiteFactory.create(unpublish_status=unpublish_status)
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-publish", kwargs={"name": website.name})
    )
    assert resp.status_code == 200
    website.refresh_from_db()

    mock_publish_website.assert_called_once_with(website.name, VERSION_LIVE)
    assert website.has_unpublished_live is False
    assert website.live_last_published_by == admin
    assert website.live_publish_status == constants.PUBLISH_STATUS_NOT_STARTED
    assert website.live_publish_status_updated_on == now
    assert website.latest_build_id_live is None
    assert website.unpublished is False
    assert website.unpublish_status is None


def test_websites_endpoint_publish_denied(mocker, drf_client):
    """A user with edit permissions should not be able to request a website publish"""
    mocker.patch("websites.views.trigger_publish")
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
    """An exception raised by the api publish call should be handled gracefully"""
    mocker.patch(
        "websites.views.trigger_publish",
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


@pytest.mark.parametrize("is_published", [True, False])
@pytest.mark.parametrize("action", ["preview", "publish"])
def test_websites_endpoint_publish_with_url(
    mocker, drf_client, ocw_site, is_published, action
):
    """Url path should be updated and content sync state reset if site is not published"""
    css = ContentSyncState.objects.filter(content__website=ocw_site)
    css.update(synced_checksum="notnull")
    mock_publish = mocker.patch("websites.views.trigger_publish")
    new_url_path = "5-new-site-fall-2020"
    old_url_path = "courses/old-path"
    ocw_site.url_path = old_url_path
    ocw_site.publish_date = now_in_utc() if is_published else None
    ocw_site.save()

    data = {"url_path": new_url_path}
    drf_client.force_login(UserFactory.create(is_superuser=True))
    drf_client.post(
        reverse(f"websites_api-{action}", kwargs={"name": ocw_site.name}), data=data
    )
    ocw_site.refresh_from_db()
    assert ocw_site.url_path == (
        ocw_site.assemble_full_url_path(new_url_path)
        if not is_published
        else old_url_path
    )
    mock_publish.assert_called_once()
    assert css.count() > 0
    for sync_state in css:
        sync_state.refresh_from_db()
        assert sync_state.synced_checksum == ("notnull" if is_published else None)


@pytest.mark.parametrize("action", ["preview", "publish"])
def test_websites_endpoint_publish_with_url_error(drf_client, ocw_site, action):
    """An error should be returned if url_path validation fails"""
    drf_client.force_login(UserFactory.create(is_superuser=True))
    ocw_site.publish_date = None
    ocw_site.save()
    response = drf_client.post(
        reverse(f"websites_api-{action}", kwargs={"name": ocw_site.name}),
        data={"url_path": "new-path=[metadata:year]"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "url_path": ["You must replace the url sections in brackets"]
    }


@pytest.mark.parametrize("action", ["preview", "publish"])
def test_websites_endpoint_publish_with_url_blank_error(drf_client, action):
    """An error should be returned if a site has no url_path yet"""
    drf_client.force_login(UserFactory.create(is_superuser=True))
    website = WebsiteFactory.create(not_published=True, url_path=None)
    response = drf_client.post(
        reverse(f"websites_api-{action}", kwargs={"name": website.name}),
        data={},
    )
    assert response.status_code == 400
    assert response.json() == {"url_path": ["The URL path cannot be blank"]}


def test_websites_endpoint_unpublish(drf_client, mocker):
    """A user with admin permissions should be able to request a website unpublish"""
    mock_unpublished_removal = mocker.patch(
        "websites.views.trigger_unpublished_removal"
    )
    now = datetime.datetime(2020, 1, 1, tzinfo=pytz.utc)
    mocker.patch("websites.views.now_in_utc", return_value=now)
    website = WebsiteFactory.create()
    mocker.patch("content_sync.tasks.Website.objects.get", return_value=website)
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-unpublish", kwargs={"name": website.name})
    )
    assert resp.status_code == 200
    website.refresh_from_db()

    mock_unpublished_removal.assert_called_once()
    assert website.unpublished is True
    assert website.unpublish_status == constants.PUBLISH_STATUS_NOT_STARTED
    assert website.last_unpublished_by == admin


def test_websites_endpoint_unpublish_denied(drf_client, mocker):
    """A user with edit permissions should not be able to request a website unpublish"""
    website = WebsiteFactory.create()
    mocker.patch("content_sync.tasks.Website.objects.get", return_value=website)
    editor = UserFactory.create()
    editor.groups.add(website.editor_group)
    drf_client.force_login(editor)
    resp = drf_client.post(
        reverse("websites_api-unpublish", kwargs={"name": website.name})
    )
    assert resp.status_code == 500
    assert resp.data == {
        "details": "You do not have permission to perform this action."
    }


def test_websites_endpoint_unpublish_error(drf_client, mocker):
    """An exception raised by the api publish call should be handled gracefully"""
    mocker.patch(
        "websites.views.trigger_unpublished_removal",
        side_effect=[HTTPError("oops")],
    )
    website = WebsiteFactory.create()
    mocker.patch("content_sync.tasks.Website.objects.get", return_value=website)
    admin = UserFactory.create()
    admin.groups.add(website.admin_group)
    drf_client.force_login(admin)
    resp = drf_client.post(
        reverse("websites_api-unpublish", kwargs={"name": website.name})
    )
    assert resp.status_code == 500
    assert resp.data == {"details": "oops"}


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
        WebsiteContentFactory.create(website=website, type="sitemetadata")
        resp = drf_client.get(
            reverse("websites_api-detail", kwargs={"name": website.name})
        )
        assert resp.status_code == 403 if not user else 404


def test_websites_endpoint_sorting(drf_client, websites, settings):
    """Response should be sorted according to query parameter"""
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    resp = drf_client.get(
        reverse("websites_api-list"),
        {"sort": "title", "type": settings.OCW_COURSE_STARTER_SLUG},
    )
    for idx, course in enumerate(sorted(websites.courses, key=lambda site: site.title)):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)


@pytest.mark.parametrize("published", [True, False])
def test_websites_endpoint_publish_sorting(drf_client, published, websites):  # pylint: disable=unused-argument
    """Should be able to filter to just published or not"""
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    resp = drf_client.get(reverse("websites_api-list"), {"published": published})
    if published:
        assert resp.data.get("count") == 5
        expected_uids = [
            str(site.uuid) for site in (*websites.courses, *websites.noncourses)
        ]
    else:
        assert resp.data.get("count") == 4
        expected_uids = [str(site.uuid) for site in websites.not_published]
    assert sorted([site["uuid"] for site in resp.data["results"]]) == sorted(
        expected_uids
    )


def test_website_endpoint_search(drf_client):
    """Should limit the queryset based on the search param"""
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)

    WebsiteFactory.create(title="Apple", name="Bacon", short_id="Cheese").save()
    WebsiteFactory.create(title="Xylophone", name="Yellow", short_id="Zebra").save()
    WebsiteFactory.create(
        title="U.S. Military Power",
        name="17-482-u-s-military-power-spring-2015",
        short_id="17.482-Spring-2015",
    ).save()
    WebsiteFactory.create(
        title="Biomedical Signal and Image Processing",
        name="hst-582j-biomedical-signal-and-image-processing-spring-2007",
        short_id="HST.582J-Spring-2007",
    ).save()
    for word in ["Apple", "Bacon", "Cheese"]:
        resp = drf_client.get(reverse("websites_api-list"), {"search": word})
        assert [website["title"] for website in resp.data.get("results")] == ["Apple"]
    for word in ["Xylophone", "Yellow", "Zebra"]:
        resp = drf_client.get(reverse("websites_api-list"), {"search": word})
        assert [website["title"] for website in resp.data.get("results")] == [
            "Xylophone"
        ]
    for word in ["U.S. military", "17-482", "17.482"]:
        resp = drf_client.get(reverse("websites_api-list"), {"search": word})
        assert [website["title"] for website in resp.data.get("results")] == [
            "U.S. Military Power"
        ]
    for word in ["signal and image", "HsT.582", "hSt-582"]:
        resp = drf_client.get(reverse("websites_api-list"), {"search": word})
        assert [website["title"] for website in resp.data.get("results")] == [
            "Biomedical Signal and Image Processing"
        ]


def test_website_endpoint_empty_search(drf_client):
    """Should limit the queryset based on the search param"""
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    WebsiteFactory.create()
    WebsiteFactory.create()
    WebsiteFactory.create()
    resp = drf_client.get(reverse("websites_api-list"), {"search": ""})
    expected_uuids = sorted([str(site.uuid) for site in Website.objects.all()])
    assert expected_uuids == sorted([site["uuid"] for site in resp.data["results"]])


def test_websites_autogenerate_name(drf_client):
    """Website POST endpoint should auto-generate a name if one is not supplied"""
    superuser = UserFactory.create(is_superuser=True)
    drf_client.force_login(superuser)
    starter = WebsiteStarterFactory.create(
        source=constants.STARTER_SOURCE_GITHUB,
        status=constants.WebsiteStarterStatus.ACTIVE,
    )
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


def test_website_starters_list(settings, drf_client, course_starter):
    """Website starters endpoint should return a serialized list"""
    settings.FEATURES[features.USE_LOCAL_STARTERS] = False
    new_starter = WebsiteStarterFactory.create(
        source=constants.STARTER_SOURCE_GITHUB,
        status=constants.WebsiteStarterStatus.ACTIVE,
    )
    resp = drf_client.get(reverse("website_starters_api-list"))
    expected_starters = [course_starter, new_starter]
    serialized_data = WebsiteStarterSerializer(expected_starters, many=True).data
    assert len(resp.data) == len(expected_starters)
    assert sorted(resp.data, key=lambda _starter: _starter["id"]) == sorted(
        serialized_data, key=lambda _starter: _starter["id"]
    )


def test_website_starters_retrieve(drf_client):
    """Website starters endpoint should return a single serialized starter"""
    starter = WebsiteStarterFactory.create(
        source=constants.STARTER_SOURCE_GITHUB,
        status=constants.WebsiteStarterStatus.ACTIVE,
    )
    resp = drf_client.get(
        reverse("website_starters_api-detail", kwargs={"pk": starter.id})
    )
    assert resp.json() == WebsiteStarterDetailSerializer(instance=starter).data


@pytest.mark.parametrize(
    ("use_local_starters", "exp_result_count"),
    [[True, 4], [False, 2]],  # noqa: PT007
)
def test_website_starters_local(
    settings, drf_client, use_local_starters, exp_result_count
):
    """Website starters endpoint should only return local starters if a feature flag is set to True"""
    settings.FEATURES[features.USE_LOCAL_STARTERS] = use_local_starters
    WebsiteStarterFactory.create_batch(
        2,
        source=factory.Iterator(
            [constants.STARTER_SOURCE_LOCAL, constants.STARTER_SOURCE_GITHUB]
        ),
        status=factory.Iterator([constants.WebsiteStarterStatus.ACTIVE]),
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
    settings.GIT_TOKEN = "git-token"  # noqa: S105
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
    ("resourcetype", "filter_type", "search", "expected_num_results"),
    [
        ["Image", "page", "text2", 1],  # noqa: PT007
        ["Image", "page", "", 3],  # noqa: PT007
        ["Image", "", "text2", 1],  # noqa: PT007
        ["Image", "", "", 3],  # noqa: PT007
        ["", "page", "text2", 1],  # noqa: PT007
        ["", "page", "", 5],  # noqa: PT007
        ["", "", "text2", 1],  # noqa: PT007
        ["", "", "", 6],  # noqa: PT007
        ["", "", "myfile3", 1],  # noqa: PT007
        ["", "", "myfile", 5],  # noqa: PT007
        ["", "", ".png", 5],  # noqa: PT007
        ["", "", ".p", 5],  # noqa: PT007
        ["", "", ".pdf", 0],  # noqa: PT007
        ["", "", "test", 0],  # noqa: PT007
        ["", "", "courses", 0],  # noqa: PT007
    ],
)
def test_websites_content_list(  # pylint: disable=too-many-locals  # noqa: PLR0913
    drf_client,
    detailed_list,
    global_admin_user,
    resourcetype,
    filter_type,
    search,
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
            metadata={"resourcetype": "Image" if num % 2 == 0 else "Video"},
            file=f"courses/my-test-site/myFile{num + 1}.png",
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
    if resourcetype:
        query_params["resourcetype"] = resourcetype

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

    if resourcetype:
        contents = [
            content
            for content in contents
            if content.metadata.get("resourcetype") == resourcetype
        ]

    sorted_contents = sorted(
        contents, key=lambda _content: _content.updated_on, reverse=True
    )
    # we set it up so Image resources are every other result, so step by 2 to account for that if filtering
    for idx in range(0, len(sorted_contents), 2 if resourcetype else 1):
        content = sorted_contents[idx]
        result = results[idx]

        assert content.title == result["title"]
        assert str(content.text_id) == result["text_id"]
        assert content.type == result["type"]
        if detailed_list:
            # metadata appears because the detail serializer was used
            assert content.metadata == result["metadata"]
        else:
            assert "metadata" not in result


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


@pytest.mark.parametrize("published", [True, False])
def test_websites_content_publish_sorting(drf_client, global_admin_user, published):  # pylint: disable=unused-argument
    """Should be able to filter to just published or not"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create(published=True)
    unpublished = WebsiteContentFactory.create_batch(
        3,
        website=website,
        # they were created after the publish date
        created_on=website.publish_date + datetime.timedelta(days=2),
    )

    published = WebsiteContentFactory.create_batch(
        3,
        website=website,
    )

    for content in published:
        content.created_on = website.publish_date - datetime.timedelta(days=2)
        content.save()

    api_url = reverse(
        "websites_content_api-list",
        kwargs={
            "parent_lookup_website": website.name,
        },
    )
    resp = drf_client.get(api_url, {"published": published})
    content = published if published else unpublished
    expected_ids = sorted([c.text_id for c in content])

    assert resp.data["count"] == 3
    assert expected_ids == sorted([c["text_id"] for c in resp.data["results"]])


def test_websites_content_gdrive_sync(mocker, drf_client, permission_groups):
    """The endpoint should kick off a task to sync Google Drive files for the website"""
    mock_sync = mocker.patch("websites.views.import_website_files.delay")
    website = permission_groups.websites[0]
    drf_client.force_login(permission_groups.site_editor)
    resp = drf_client.post(
        reverse(
            "websites_content_api-gdrive-sync",
            kwargs={"parent_lookup_website": website.name},
        )
    )
    mock_sync.assert_called_once_with(website.name)
    assert resp.status_code == 200


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


def test_websites_content_create_with_textid(drf_client, global_admin_user):
    """If a text_id is added when POSTing to the WebsiteContent, we should use that instead of creating a uuid"""
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    payload = {
        "type": "sitemetadata",
        "metadata": {
            "course_title": "a title",
        },
        "text_id": "sitemetadata",
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
    assert content.type == payload["type"]
    assert resp.data["text_id"] == str(content.text_id)
    assert content.text_id == "sitemetadata"


@pytest.mark.parametrize(
    ("root_url_path", "expected_prefix"),
    [
        ["", ""],  # noqa: PT007
        ["/", ""],  # noqa: PT007
        ["/test/sites/", "test/sites"],  # noqa: PT007
    ],
)
def test_websites_content_create_with_upload(  # noqa: PLR0913
    mocker, drf_client, global_admin_user, file_upload, root_url_path, expected_prefix
):
    """Uploading a file when creating a new WebsiteContent object should work"""
    mime_type = "text/doof"
    mocker.patch("websites.serializers.detect_mime_type", return_value=mime_type)
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
    assert content.metadata["file_type"] == mime_type
    assert resp.data["text_id"] == str(content.text_id)


def test_websites_content_edit_with_upload(
    mocker, drf_client, global_admin_user, file_upload
):
    """Uploading a file when editing a new WebsiteContent object should work"""
    mime_type = "text/doof"
    mocker.patch("websites.serializers.detect_mime_type", return_value=mime_type)
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
    assert content.metadata["file_type"] == mime_type
    assert resp.data["text_id"] == str(content.text_id)


@pytest.mark.parametrize(
    ("has_matching_config_item", "is_page_content", "exp_page_content_field"),
    [
        [True, True, True],  # noqa: PT007
        [False, True, False],  # noqa: PT007
        [True, False, False],  # noqa: PT007
    ],
)
def test_content_create_page_content(  # noqa: PLR0913
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


@pytest.mark.parametrize(
    ("title", "expected_filename_base"),
    [
        ["My Title", "my-title"],  # noqa: PT007
        [  # noqa: PT007
            constants.CONTENT_FILENAMES_FORBIDDEN[0],
            f"{constants.CONTENT_FILENAMES_FORBIDDEN[0]}-{constants.CONTENT_TYPE_RESOURCE}",
        ],
    ],
)
def test_content_create_page_added_context(
    mocker, drf_client, global_admin_user, title, expected_filename_base
):
    """
    POSTing to the WebsiteContent list view without a filename should add a generated filename
    """
    patched_get_filename = mocker.patch(
        "websites.views.get_valid_new_filename",
        return_value=f"{expected_filename_base}-100",
    )
    drf_client.force_login(global_admin_user)
    website = WebsiteFactory.create()
    payload = {
        "title": title,
        "markdown": "some markdown",
        "type": constants.CONTENT_TYPE_RESOURCE,
    }
    # "folder" path for the config item with type="blog" in basic-site-config.yml
    expected_dirpath = "content/resource"
    expected_filename = f"{expected_filename_base}-100"
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
        website_pk=website.pk,
        dirpath=expected_dirpath,
        filename_base=expected_filename_base,
    )
    content = website.websitecontent_set.order_by("-created_on").first()
    assert content.website == website
    assert content.filename == expected_filename
    # "folder" path for the config item with type="blog" in basic-site-config.yml
    assert content.dirpath == expected_dirpath
    assert content.is_page_content is True


def test_content_create_page_added_context_with_slug(drf_client, global_admin_user):
    """
    POSTing to the WebsiteContent list view without a filename should add a generated filename based on the slug field
    """
    drf_client.force_login(global_admin_user)
    title = "My Title"
    website = WebsiteFactory.create()
    website.starter.config["collections"][0]["slug"] = "text_id"
    website.starter.save()
    payload = {
        "title": title,
        "markdown": "some markdown",
        "type": "blog",
    }
    # "folder" path for the config item with type="blog" in basic-site-config.yml
    expected_dirpath = "content/blog"
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
    content = website.websitecontent_set.order_by("-created_on").first()
    assert content.website == website
    assert content.filename == content.text_id
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


@pytest.mark.parametrize(
    "status", [constants.PUBLISH_STATUS_STARTED, constants.PUBLISH_STATUS_ERRORED]
)
@pytest.mark.parametrize("version", [VERSION_LIVE, VERSION_DRAFT])
@pytest.mark.parametrize("unpublished", [True, False])
def test_websites_endpoint_pipeline_status(  # noqa: PLR0913
    settings, mocker, drf_client, permission_groups, version, status, unpublished
):
    """The pipeline_complete endpoint should send notifications to site owner/admins"""
    mock_update_status = mocker.patch("websites.views.update_website_status")
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    website = permission_groups.websites[0]
    drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.API_BEARER_TOKEN}")
    data = {"version": version, "status": f"{status}"}
    if unpublished:
        data["unpublished"] = True
    resp = drf_client.post(
        reverse("websites_api-pipeline-status", kwargs={"name": website.name}),
        data=data,
    )
    mock_update_status.assert_called_once_with(
        website,
        version,
        status,
        mocker.ANY,
        unpublished=(unpublished and version == VERSION_LIVE),
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("token", ["abc123", None])
def test_websites_endpoint_pipeline_status_denied(
    settings, drf_client, permission_groups, token
):
    """The pipeline_complete endpoint should raise a permission error without a valid token"""
    settings.API_BEARER_TOKEN = token
    website = permission_groups.websites[0]
    drf_client.credentials(HTTP_AUTHORIZATION="Bearer wrong-token")
    resp = drf_client.post(
        reverse("websites_api-pipeline-status", kwargs={"name": website.name}),
        json={"version": VERSION_LIVE, "status": constants.PUBLISH_STATUS_STARTED},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("unpublished", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_mass_build_endpoint_list(settings, drf_client, version, unpublished):
    """The WebsitePublishView endpoint should return the appropriate info for correctly filtered sites"""
    now = now_in_utc()
    draft_published = WebsiteFactory.create_batch(
        2,
        draft_publish_date=now,
        publish_date=None,
        first_published_to_production=now,
        unpublish_status=constants.PUBLISH_STATUS_NOT_STARTED if unpublished else None,
        with_url_path=True,
    )
    live_published = WebsiteFactory.create_batch(
        2,
        draft_publish_date=None,
        publish_date=now_in_utc(),
        first_published_to_production=now,
        unpublish_status=constants.PUBLISH_STATUS_NOT_STARTED if unpublished else None,
        with_url_path=True,
    )
    expected_sites = draft_published if version == VERSION_DRAFT else live_published
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.API_BEARER_TOKEN}")
    resp = drf_client.get(f"{reverse('mass_build_api-list')}?version={version}")
    assert resp.status_code == 200
    site_dict = {site["name"]: site for site in resp.data["sites"]}
    if not unpublished or version == VERSION_DRAFT:
        assert len(site_dict.keys()) == 2
        for expected_site in expected_sites:
            publish_site = site_dict.get(expected_site.name, None)
            assert publish_site is not None
            assert publish_site["short_id"] == expected_site.short_id
    else:
        assert len(site_dict.keys()) == 0


def test_mass_build_endpoint_list_bad_version(settings, drf_client):
    """The WebsiteMassBuildView endpoint should return a 400 if the version parameter is invalid"""
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.API_BEARER_TOKEN}")
    resp = drf_client.get(f"{reverse('mass_build_api-list')}?version=null")
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_token", ["wrongtoken", None])
def test_mass_build_endpoint_list_bad_token(settings, drf_client, bad_token):
    """The WebsiteMassBuildView endpoint should return a 403 if the token is invalid or missing"""
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    if bad_token:
        drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {bad_token}")
    resp = drf_client.get(f"{reverse('mass_build_api-list')}?version={VERSION_LIVE}")
    assert resp.status_code == 403


def test_unpublished_removal_endpoint_list(settings, drf_client):
    """The WebsiteUnpublishViewSet endpoint should return the appropriate info for correctly filtered sites"""
    published_sites = [
        WebsiteFactory.create(
            draft_publish_date=None,
            publish_date=now_in_utc(),
        ),
        WebsiteFactory.create(
            publish_date=now_in_utc(),
            unpublish_status=PUBLISH_STATUS_SUCCEEDED,
        ),
    ]
    expected_sites = WebsiteFactory.create_batch(
        2, publish_date=now_in_utc(), unpublished=True
    )
    for site in [*published_sites, *expected_sites]:
        WebsiteContentFactory.create(
            type=CONTENT_TYPE_METADATA, website=site, metadata={}
        )
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.API_BEARER_TOKEN}")
    resp = drf_client.get(f"{reverse('unpublished_removal_api-list')}")
    assert resp.status_code == 200
    site_dict = {site["name"]: site for site in resp.data["sites"]}
    assert len(site_dict.keys()) == 2
    for expected_site in expected_sites:
        publish_site = site_dict.get(expected_site.name, None)
        assert publish_site is not None
        assert publish_site["name"] == expected_site.name
        assert publish_site["site_uid"] == expected_site.uuid.hex


@pytest.mark.parametrize("bad_token", ["wrongtoken", None])
def test_unpublished_removal_endpoint_list_bad_token(settings, drf_client, bad_token):
    """The WebsiteUnpublishViewSet endpoint should return a 403 if the token is invalid or missing"""
    settings.API_BEARER_TOKEN = "abc123"  # noqa: S105
    if bad_token:
        drf_client.credentials(HTTP_AUTHORIZATION=f"Bearer {bad_token}")
    resp = drf_client.get(f"{reverse('unpublished_removal_api-list')}")
    assert resp.status_code == 403
