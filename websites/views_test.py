""" Tests for websites views """
from types import SimpleNamespace

import factory
import pytest
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc

from main import features
from main.constants import ISO_8601_FORMAT
from websites.constants import (
    COURSE_STARTER_SLUG,
    STARTER_SOURCE_GITHUB,
    STARTER_SOURCE_LOCAL,
)
from websites.factories import WebsiteFactory, WebsiteStarterFactory
from websites.serializers import (
    WebsiteDetailSerializer,
    WebsiteStarterDetailSerializer,
    WebsiteStarterSerializer,
)


# pylint:disable=redefined-outer-name

pytestmark = pytest.mark.django_db


@pytest.fixture
def websites(course_starter):
    """ Create some websites for tests """
    courses = WebsiteFactory.create_batch(3, published=True, starter=course_starter)
    noncourses = WebsiteFactory.create_batch(2, published=True)
    WebsiteFactory.create(unpublished=True, starter=course_starter)
    WebsiteFactory.create(future_publish=True)
    return SimpleNamespace(courses=courses, noncourses=noncourses)


@pytest.mark.parametrize("website_type", [COURSE_STARTER_SLUG, None])
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
            COURSE_STARTER_SLUG if filter_by_type else site.starter.slug
        )
        assert resp.data.get("results")[idx]["publish_date"] <= now.strftime(
            ISO_8601_FORMAT
        )


def test_websites_endpoint_detail(drf_client):
    """Test new websites endpoint for details"""
    website = WebsiteFactory.create()
    resp = drf_client.get(reverse("websites_api-detail", kwargs={"pk": website.uuid}))
    assert resp.json() == WebsiteDetailSerializer(instance=website).data


def test_websites_endpoint_sorting(drf_client, websites):
    """ Response should be sorted according to query parameter """
    resp = drf_client.get(
        reverse("websites_api-list"), {"sort": "title", "type": COURSE_STARTER_SLUG}
    )
    for idx, course in enumerate(sorted(websites.courses, key=lambda site: site.title)):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)


def test_website_starters_list(drf_client, course_starter):
    """ Website starters endpoint should return a serialized list """
    new_starter = WebsiteStarterFactory.create(source=STARTER_SOURCE_GITHUB)
    resp = drf_client.get(reverse("website_starters_api-list"))
    resp_results = resp.data.get("results")
    serialized_data = WebsiteStarterSerializer(
        [course_starter, new_starter], many=True
    ).data
    assert len(resp_results) == 2
    assert resp_results == serialized_data


def test_website_starters_retrieve(drf_client):
    """ Website starters endpoint should return a single serialized starter """
    starter = WebsiteStarterFactory.create(source=STARTER_SOURCE_GITHUB)
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
        2, source=factory.Iterator([STARTER_SOURCE_LOCAL, STARTER_SOURCE_GITHUB])
    )
    resp = drf_client.get(reverse("website_starters_api-list"))
    resp_results = resp.data.get("results")
    assert len(resp_results) == exp_result_count
