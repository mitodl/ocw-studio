""" Tests for ocw_import.api """
import json
import re

import pytest
from moto import mock_s3

from ocw_import.api import get_short_id, import_ocw2hugo_course
from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PREFIX,
    get_ocw2hugo_path,
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

TEST_OCW2HUGO_PATH = get_ocw2hugo_path("./test_ocw2hugo")


@mock_s3
def test_import_ocw2hugo_course_content(mocker, settings):
    """ import_ocw2hugo_course should create a new website plus content"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    filenames = [f"file-{i}" for i in range(100)]
    get_valid_new_filename_mock = mocker.patch(
        "ocw_import.api.get_valid_new_filename", side_effect=filenames
    )
    website_starter = WebsiteStarterFactory.create()
    import_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, starter_id=website_starter.id
    )
    website = Website.objects.get(name=name)
    assert website.starter == website_starter
    assert website.source == WEBSITE_SOURCE_OCW_IMPORT
    assert website.short_id == "1.050-fall-2007"
    with open(f"{TEST_OCW2HUGO_PATH}/{name}/data/course_legacy.json", "r") as infile:
        assert json.dumps(website.metadata, sort_keys=True) == json.dumps(
            json.load(infile), sort_keys=True
        )
    assert (
        WebsiteContent.objects.filter(website=website, type=CONTENT_TYPE_PAGE).count()
        == 7
    )
    assert (
        WebsiteContent.objects.filter(
            website=website, type=CONTENT_TYPE_RESOURCE
        ).count()
        == 67
    )

    related_page = WebsiteContent.objects.get(
        text_id="4f5c3926-e4d5-6974-7f16-131a6f692568"
    )
    assert related_page.type == CONTENT_TYPE_PAGE
    assert related_page.metadata.get("title") == "Related Resources"
    assert related_page.filename == "file-3"
    assert related_page.dirpath == "content/pages"
    get_valid_new_filename_mock.assert_any_call(
        website.pk,
        related_page.dirpath,
        "related-resources",
        related_page.text_id,
    )

    child_page = WebsiteContent.objects.get(
        text_id="6a79c92a-7b81-44f5-b23e-870c73367065"
    )
    assert child_page.parent == WebsiteContent.objects.get(
        text_id="a38d0e39-8dc8-4a90-b38f-96f349e73c26"
    )

    lecture_pdf = WebsiteContent.objects.get(
        text_id="7f91d524-57aa-ef80-93c5-8a43f10a099b"
    )
    assert lecture_pdf.type == CONTENT_TYPE_RESOURCE
    assert lecture_pdf.metadata.get("file_type") == "application/pdf"
    assert lecture_pdf.filename == "file-20"
    assert lecture_pdf.dirpath == "content/resources"
    assert lecture_pdf.file == re.sub(
        r"^/?coursemedia", "courses", lecture_pdf.metadata.get("file_location")
    )
    get_valid_new_filename_mock.assert_any_call(
        website.pk,
        lecture_pdf.dirpath,
        "lec1",
        lecture_pdf.text_id,
    )


@mock_s3
def test_import_ocw2hugo_course_metadata(settings, root_website):
    """ import_ocw2hugo_course should also populate site metadata"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
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
        .values("title", "dirpath", "is_page_content", "metadata")
        .order_by("title")
    ) == [
        {
            "title": "Prof. Franz-Josef Ulm",
            "dirpath": "content/instructors",
            "is_page_content": True,
            "metadata": {
                "first_name": "Franz-Josef",
                "middle_initial": "",
                "last_name": "Ulm",
                "salutation": "Prof.",
                "headless": True,
            },
        },
        {
            "title": "Prof. Markus Buehler",
            "dirpath": "content/instructors",
            "is_page_content": True,
            "metadata": {
                "first_name": "Markus",
                "middle_initial": "",
                "last_name": "Buehler",
                "salutation": "Prof.",
                "headless": True,
            },
        },
    ]

    website = Website.objects.get(name=name)
    metadata = WebsiteContent.objects.get(website=website, type=CONTENT_TYPE_METADATA)
    assert metadata.metadata == {
        "level": "Undergraduate",
        "topics": [
            ["Engineering", "Mechanical Engineering", "Solid Mechanics"],
            ["Engineering", "Aerospace Engineering", "Structural Mechanics"],
            ["Engineering", "Civil Engineering", "Structural Engineering"],
        ],
        "instructors": {
            "content": [
                "0b39fff4-81fb-b968-8e2d-a0ce16ece1d4",
                "95041ae9-ab5b-75af-f711-13fcd917f464",
            ],
            "website": "ocw-www",
        },
        "course_title": "Engineering Mechanics I",
        "course_description": "This subject provides an introduction to the mechanics of materials and structures. You will be introduced to and become familiar with all relevant physical properties and fundamental laws governing the behavior of materials and structures and you will learn how to solve a variety of problems of interest to civil and environmental engineers. While there will be a chance for you to put your mathematical skills obtained in 18.01, 18.02, and eventually 18.03 to use in this subject, the emphasis is on the physical understanding of why a material or structure behaves the way it does in the engineering design of materials and structures.\n",
        "department_numbers": ["1"],
        "extra_course_numbers": "",
        "primary_course_number": "1.050",
        "learning_resource_types": ["Problem Sets", "Lecture Notes"],
    }


@mock_s3
def test_import_ocw2hugo_course_bad_date(mocker, settings):
    """ Website publish date should be null if the JSON date can't be parsed """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mocker.patch("ocw_import.api.parse_date", side_effect=ValueError())
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    assert website.publish_date is None


@mock_s3
def test_import_ocw2hugo_course_noncourse(settings):
    """ Website should not be created for a non-course """
    setup_s3(settings)
    name = "biology"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).count() == 0


@mock_s3
def test_import_ocw2hugo_course_log_exception(mocker, settings):
    """ Log an exception if the website cannot be saved/updated """
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mocker.patch("ocw_import.api.parse_date", return_value="Invalid date")
    mock_log = mocker.patch("ocw_import.api.log.exception")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).first() is None
    mock_log.assert_called_once_with("Error saving website %s", s3_key)


@mock_s3
def test_import_ocw2hugo_content_log_exception(mocker, settings):
    """ Log an exception if the website content cannot be saved/updated """
    setup_s3(settings)
    name = "1-201j-transportation-systems-analysis-demand-and-economics-fall-2008"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mock_log = mocker.patch("ocw_import.api.log.exception")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert mock_log.call_count == 1
    mock_log.assert_called_once_with(
        "Error saving WebsiteContent for %s", f"{name}/content/pages/test_no_uid.md"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "course_num, term, expected_id",
    [
        ["6.0001", "", "6.0001"],
        ["5.3", "Spring 2022", "5.3-spring-2022"],
        ["5.3", "January IAP 2011", "5.3-january-iap-2011"],
        [None, "January IAP 2011", None],
    ],
)
def test_get_short_id(course_num, term, expected_id):
    """ get_short_id should return expected values, or raise an error if no course number"""
    metadata = {"primary_course_number": course_num, "term": f"{term}"}
    if expected_id:
        short_id = get_short_id(metadata)
        assert short_id == expected_id
        for i in range(1, 4):
            WebsiteFactory.create(short_id=short_id)
            short_id = get_short_id(metadata)
            assert short_id == f"{expected_id}-{i+1}"
    else:
        with pytest.raises(ValueError):
            get_short_id(metadata)


@mock_s3
def test_import_ocw2hugo_menu(settings, mocker):
    """ Website publish date should be null if the JSON date can't be parsed """
    uuid4_hex = "a" * 32
    mocker.patch("uuid.uuid4").return_value.hex = uuid4_hex
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    navmenu = WebsiteContent.objects.get(website=website, type="navmenu")
    assert navmenu.metadata == {
        "leftnav": [
            {
                "url": "/pages/syllabus",
                "name": "Syllabus",
                "weight": 10,
                "identifier": "96c31e82-69f0-6d67-daee-8272526ac56a",
            },
            {
                "url": "/pages/calendar",
                "name": "Calendar",
                "weight": 20,
                "identifier": "ff5e415d-cded-bcfc-d6b2-c4a96377207c",
            },
            {
                "url": "/pages/lecture-notes",
                "name": "Lecture Notes",
                "weight": 30,
                "identifier": "dec40ff4-e8ca-636f-c6db-d88880914a96",
            },
            {
                "url": "/pages/assignments",
                "name": "Assignments",
                "weight": 40,
                "identifier": "8e344ad5-a553-4368-9048-9e95e736657a",
            },
            {
                "url": "/pages/related-resources",
                "name": "Related Resources",
                "weight": 50,
                "identifier": "4f5c3926-e4d5-6974-7f16-131a6f692568",
            },
            {
                "url": "https://openlearning.mit.edu/",
                "name": "Open Learning",
                "identifier": f"external-{uuid4_hex}",
            },
        ]
    }
