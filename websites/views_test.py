""" Tests for websites views """
import pytest
from django.urls import reverse

from main.utils import now_in_utc
from websites.constants import WEBSITE_TYPE_COURSE
from websites.factories import WebsiteFactory
from fixtures.common import drf_client  # pylint: disable=unused-import

# pylint:disable=redefined-outer-name


@pytest.mark.django_db
def test_new_courses_endpoint(drf_client):
    """Test new course websites endpoint"""
    new_courses = sorted(
        WebsiteFactory.create_batch(3, published=True, is_course=True),
        reverse=True,
        key=lambda course: course.publish_date,
    )
    now = now_in_utc()

    # These should not be returned
    WebsiteFactory.create(unpublished=True, is_course=True)
    WebsiteFactory.create(future_publish=True, is_course=True)
    WebsiteFactory.create(published=True, not_course=True)

    resp = drf_client.get(reverse("websites_api-list") + "courses/new/")
    assert resp.data.get("count") == 3
    for idx, course in enumerate(new_courses):
        assert resp.data.get("results")[idx]["uuid"] == str(course.uuid)
        assert resp.data.get("results")[idx]["type"] == WEBSITE_TYPE_COURSE
        assert resp.data.get("results")[idx]["publish_date"] <= now.strftime("%Y-%m-%dT%H:%M:%SZ")
