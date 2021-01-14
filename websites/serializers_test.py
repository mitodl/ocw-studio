""" Tests for websites.serializers """
import pytest

from websites.constants import WEBSITE_TYPE_COURSE
from websites.factories import WebsiteFactory
from websites.serializers import WebsiteSerializer


@pytest.mark.django_db
def test_serialize_website_course():
    """
    Verify that a serialized website course contains expected fields
    """
    course = WebsiteFactory(is_course=True)
    serializer = WebsiteSerializer(course)
    assert serializer.data["type"] == WEBSITE_TYPE_COURSE
    assert serializer.data["url_path"] == course.url_path
    assert serializer.data["publish_date"] == course.publish_date.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert serializer.data["metadata"] == course.metadata
