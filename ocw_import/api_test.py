""" Tests for ocw_import.api """
import json

import pytest
from moto import mock_s3

from ocw_import.api import import_ocw2hugo_course
from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PATH,
    TEST_OCW2HUGO_PREFIX,
    setup_s3,
)
from websites.constants import (
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.factories import WebsiteStarterFactory
from websites.models import Website, WebsiteContent
import logging

log = logging.getLogger(__name__)


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course(settings):
    """ import_ocw2hugo_course should create a new website plus content"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    website_starter = WebsiteStarterFactory.create()
    import_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, starter_id=website_starter.id
    )
    website = Website.objects.get(name=name)
    assert website.starter == website_starter
    assert website.source == WEBSITE_SOURCE_OCW_IMPORT
    with open(f"{TEST_OCW2HUGO_PATH}/{name}/data/course.json", "r") as infile:
        assert json.dumps(website.metadata, sort_keys=True) == json.dumps(
            json.load(infile), sort_keys=True
        )
    assert WebsiteContent.objects.filter(type=CONTENT_TYPE_PAGE).count() == 6
    assert WebsiteContent.objects.filter(type=CONTENT_TYPE_RESOURCE).count() == 4

    home_page = WebsiteContent.objects.get(
        website=website, metadata__layout="course_home"
    )
    assert home_page.type == CONTENT_TYPE_PAGE
    assert home_page.metadata.get("layout") == "course_home"
    assert home_page.markdown.startswith(
        "This subject provides an introduction to the mechanics of materials"
    )
    assert home_page.filename == "_index"
    assert home_page.dirpath == "1-050-engineering-mechanics-i-fall-2007/content"

    related_page = WebsiteContent.objects.get(
        text_id="4f5c3926-e4d5-6974-7f16-131a6f692568"
    )
    assert related_page.type == CONTENT_TYPE_PAGE
    assert related_page.metadata.get("title") == "Related Resources"
    assert related_page.parent == WebsiteContent.objects.get(
        text_id="ba83162e-713c-c931-5ff9-bfe952c79b82"
    )
    assert related_page.filename == "_index"
    assert (
        related_page.dirpath
        == "1-050-engineering-mechanics-i-fall-2007/content/sections/related-resources"
    )

    lecture_pdf = WebsiteContent.objects.get(
        text_id="7f91d524-57aa-ef80-93c5-8a43f10a099b"
    )
    assert lecture_pdf.type == CONTENT_TYPE_RESOURCE
    assert lecture_pdf.metadata.get("file_type") == "application/pdf"
    assert lecture_pdf.filename == "lec1"
    assert (
        lecture_pdf.dirpath
        == "1-050-engineering-mechanics-i-fall-2007/content/sections/lecture-notes"
    )

    data_template = WebsiteContent.objects.get(
        website=website,
        dirpath="1-050-engineering-mechanics-i-fall-2007/data",
        filename="course",
    )
    assert data_template.title == "course.json"
    assert json.loads(data_template.metadata) == website.metadata


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_external_nav_link(settings):
    """ Website publish date should be null if the JSON date can't be parsed """
    setup_s3(settings)
    name = "7-00-covid-19-sars-cov-2-and-the-pandemic-fall-2020"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    menus = WebsiteContent.objects.get(
        website=website, dirpath=f"{name}/config/_default", filename="menus"
    )
    expected = {
        "leftnav": [
            {
                "name": "Online Publication",
                "url": "https://biology.mit.edu/undergraduate/current-students/subject-offerings/covid-19-sars-cov-2-and-the-pandemic/",
                "weight": 1000,
            }
        ]
    }
    assert json.loads(menus.metadata) == expected


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_bad_date(mocker, settings):
    """ Website publish date should be null if the JSON date can't be parsed """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    mocker.patch(
        "ocw_import.api.dateparser.parse", side_effect=["2021-01-01", ValueError()]
    )
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    assert website.publish_date is None


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_noncourse(settings):
    """ Website should not be created for a non-course """
    setup_s3(settings)
    name = "biology"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).count() == 0


@mock_s3
@pytest.mark.django_db
def test_import_ocw2hugo_course_log_exception(mocker, settings):
    """ Log an exception if the website cannot be saved/updated """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
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
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    mock_log = mocker.patch("ocw_import.api.log.error")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert mock_log.call_count == 1
    mock_log.assert_called_once_with(
        "No UUID (text ID): %s",
        "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008/content/sections/test_no_uid.md",
    )
