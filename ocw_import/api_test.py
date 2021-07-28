""" Tests for ocw_import.api """
import json

import pytest
from moto import mock_s3

from ocw_import.api import get_short_id, import_ocw2hugo_course
from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PATH,
    TEST_OCW2HUGO_PREFIX,
    setup_s3,
)
from websites.constants import (
    CONTENT_TYPE_INSTRUCTOR,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.factories import WebsiteFactory, WebsiteStarterFactory
from websites.models import Website, WebsiteContent


pytestmark = pytest.mark.django_db


@mock_s3
def test_import_ocw2hugo_course_content(settings):
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
    assert website.short_id == "1.050-fall-2007"
    with open(f"{TEST_OCW2HUGO_PATH}/{name}/data/course.json", "r") as infile:
        assert json.dumps(website.metadata, sort_keys=True) == json.dumps(
            json.load(infile), sort_keys=True
        )
    assert (
        WebsiteContent.objects.filter(website=website, type=CONTENT_TYPE_PAGE).count()
        == 6
    )
    assert (
        WebsiteContent.objects.filter(
            website=website, type=CONTENT_TYPE_RESOURCE
        ).count()
        == 3
    )

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


@mock_s3
def test_import_ocw2hugo_course_metadata(settings, root_website):
    """ import_ocw2hugo_course should also populate site metadata"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    website_starter = WebsiteStarterFactory.create()
    assert (
        WebsiteContent.objects.filter(
            website=root_website, type=CONTENT_TYPE_INSTRUCTOR
        ).count()
        == 0
    )
    import_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, starter_id=website_starter.id
    )
    assert list(
        WebsiteContent.objects.filter(type=CONTENT_TYPE_INSTRUCTOR)
        .values("title", "metadata")
        .order_by("title")
    ) == [
        {
            "title": "Franz-Josef Ulm",
            "metadata": {
                "first_name": "Franz-Josef",
                "middle_initial": "",
                "last_name": "Ulm",
                "salutation": "",
                "headless": True,
            },
        },
        {
            "title": "Markus Buehler",
            "metadata": {
                "first_name": "Markus",
                "middle_initial": "",
                "last_name": "Buehler",
                "salutation": "",
                "headless": True,
            },
        },
    ]

    website = Website.objects.get(name=name)
    metadata = WebsiteContent.objects.get(website=website, type=CONTENT_TYPE_METADATA)
    assert metadata.metadata == {
        "instructors": {
            "content": [
                "0b39fff4-81fb-b968-8e2d-a0ce16ece1d4",
                "95041ae9-ab5b-75af-f711-13fcd917f464",
            ],
            "website": "ocw-www",
        }
    }


@mock_s3
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
def test_import_ocw2hugo_course_noncourse(settings):
    """ Website should not be created for a non-course """
    setup_s3(settings)
    name = "biology"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).count() == 0


@mock_s3
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


@pytest.mark.django_db
def test_get_short_id():
    """ get_short_id should return expected values """
    course_num = "6.0001"
    semester = "Spring"
    year = "2024"
    metadata = {"primary_course_number": course_num, "term": f"{semester} {year}"}
    short_id = get_short_id(metadata)
    assert short_id == f"{course_num}-{semester.lower()}-{year}"
    for i in range(1, 4):
        WebsiteFactory.create(short_id=short_id)
        short_id = get_short_id(metadata)
        assert short_id == f"{course_num}-{semester.lower()}-{year}-{i+1}"
