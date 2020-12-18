""" Tests for websites.utils """
import json

import pytest

from moto import mock_s3

from websites.conftest import (
    setup_s3,
    TEST_OCW2HUGO_PREFIX,
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PATH,
)
from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_FILE
from websites.models import Website, WebsiteContent
from websites.utils import import_ocw2hugo_course


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course(settings):
    """ import_ocw2hugo_course should create a new website plus content"""
    setup_s3(settings)
    url_path = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}data/courses/{url_path}.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(url_path=url_path)
    with open(f"{TEST_OCW2HUGO_PATH}data/courses/{url_path}.json", "r") as infile:
        assert json.dumps(website.metadata, sort_keys=True) == json.dumps(
            json.load(infile), sort_keys=True
        )
    assert WebsiteContent.objects.filter(type="page").count() == 6
    assert WebsiteContent.objects.filter(type="file").count() == 8

    home_page = WebsiteContent.objects.get(uuid=website.uuid)
    assert home_page.type == CONTENT_TYPE_PAGE
    assert home_page.metadata.get("layout") == "course_home"
    assert home_page.markdown.startswith(
        "This subject provides an introduction to the mechanics of materials"
    )

    related_page = WebsiteContent.objects.get(uuid="4f5c3926e4d569747f16131a6f692568")
    assert related_page.type == CONTENT_TYPE_PAGE
    assert related_page.metadata.get("title") == "Related Resources"
    assert related_page.parent == WebsiteContent.objects.get(
        uuid="dec40ff4e8ca636fc6dbd88880914a96"
    )

    lecture_pdf = WebsiteContent.objects.get(uuid="7f91d52457aaef8093c58a43f10a099b")
    assert lecture_pdf.type == CONTENT_TYPE_FILE
    assert lecture_pdf.metadata.get("file_type") == "application/pdf"
    assert (
        lecture_pdf.hugo_filepath
        == "content/courses/1-050-engineering-mechanics-i-fall-2007/sections/lecture-notes/lec1.md"
    )
