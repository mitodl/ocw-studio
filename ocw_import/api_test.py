""" Tests for ocw_import.api """
import json

import pytest

from moto import mock_s3

from websites.constants import CONTENT_TYPE_PAGE, CONTENT_TYPE_FILE
from websites.factories import WebsiteStarterFactory
from websites.models import Website, WebsiteContent
from ocw_import.conftest import (
    setup_s3,
    TEST_OCW2HUGO_PREFIX,
    TEST_OCW2HUGO_PATH,
    MOCK_BUCKET_NAME,
)
from ocw_import.api import import_ocw2hugo_course


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course(settings):
    """ import_ocw2hugo_course should create a new website plus content"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}data/courses/{name}.json"
    website_starter = WebsiteStarterFactory.create()
    import_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, starter_id=website_starter.id
    )
    website = Website.objects.get(name=name)
    assert website.starter == website_starter
    with open(f"{TEST_OCW2HUGO_PATH}data/courses/{name}.json", "r") as infile:
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


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_bad_date(mocker, settings):
    """ Website publish date should be null if the JSON date can't be parsed """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}data/courses/{name}.json"
    mocker.patch(
        "ocw_import.api.dateparser.parse", side_effect=["2021-01-01", ValueError()]
    )
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    assert website.publish_date is None


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_log_exception(mocker, settings):
    """ Log an exception if the website cannot be saved/updated """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}data/courses/{name}.json"
    mocker.patch("ocw_import.api.dateparser.parse", return_value="Invalid date")
    mock_log = mocker.patch("ocw_import.api.log.exception")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).first() is None
    mock_log.assert_called_once_with("Error saving website %s", s3_key)


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_content_log_exception(mocker, settings):
    """ Log an exception if the website content cannot be saved/updated """
    setup_s3(settings)
    name = "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}data/courses/{name}.json"
    mocker.patch("ocw_import.api.uuid4", return_value="Invalid uuid")
    mock_log = mocker.patch("ocw_import.api.log.exception")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert mock_log.call_count == 1
    mock_log.assert_called_once_with(
        "Error saving WebsiteContent for %s",
        f"{TEST_OCW2HUGO_PREFIX}content/courses/1-201j-transportation-systems-analysis-demand-and-economics-fall-2008/sections/syllabus.md",
    )
