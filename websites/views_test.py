""" Tests for websites views """
from types import SimpleNamespace

import pytest
from django.urls import reverse

from main.constants import ISO_8601_FORMAT
from main.utils import now_in_utc
from websites.constants import WEBSITE_TYPE_COURSE
from websites.factories import WebsiteFactory
from fixtures.common import drf_client  # pylint: disable=unused-import

# pylint:disable=redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.fixture
def websites():
    """ Create some websites for tests """
    courses = WebsiteFactory.create_batch(3, published=True, is_course=True)
    noncourses = WebsiteFactory.create_batch(2, published=True, not_course=True)
    WebsiteFactory.create(unpublished=True, is_course=True)
    WebsiteFactory.create(future_publish=True, is_course=True)
    return SimpleNamespace(courses=courses, noncourses=noncourses)


@pytest.mark.parametrize("website_type", [WEBSITE_TYPE_COURSE, None])
def test_websites_endpoint(drf_client, website_type, websites):
    """Test new websites endpoint"""
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
    for idx, course in enumerate(
        sorted(expected_websites, reverse=True, key=lambda site: site.publish_date)
    ):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)
        assert resp.data.get("results")[idx]["type"] == (
            WEBSITE_TYPE_COURSE if filter_by_type else course.type
        )
        assert resp.data.get("results")[idx]["publish_date"] <= now.strftime(
            ISO_8601_FORMAT
        )


def test_websites_endpoint_sorting(drf_client, websites):
    """ Response should be sorted according to query parameter """
    resp = drf_client.get(
        reverse("websites_api-list"), {"sort": "title", "type": WEBSITE_TYPE_COURSE}
    )
    for idx, course in enumerate(sorted(websites.courses, key=lambda site: site.title)):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)
