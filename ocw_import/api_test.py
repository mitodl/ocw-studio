"""Tests for ocw_import.api"""

import json
import re
from unittest.mock import Mock, patch

import pytest
from moto import mock_aws

from ocw_import.api import (
    get_learning_resource_types,
    get_short_id,
    import_ocw2hugo_course,
    import_ocw2hugo_sitemetadata,
    update_content_from_s3_data,
    update_ocw2hugo_course,
)
from ocw_import.conftest import (
    MOCK_BUCKET_NAME,
    TEST_OCW2HUGO_PREFIX,
    get_ocw2hugo_path,
    setup_s3,
)
from ocw_import.constants import OCW_TYPE_ASSIGNMENTS, OCW_TYPE_LECTURE_NOTES
from websites.constants import (
    CONTENT_TYPE_INSTRUCTOR,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    WEBSITE_SOURCE_OCW_IMPORT,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import Website, WebsiteContent

pytestmark = pytest.mark.django_db

TEST_OCW2HUGO_PATH = get_ocw2hugo_path("./test_ocw2hugo")


@mock_aws
def test_import_ocw2hugo_course_content(mocker, settings):
    """import_ocw2hugo_course should create a new website plus content"""
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
    with open(  # noqa: PTH123
        f"{TEST_OCW2HUGO_PATH}/{name}/data/course_legacy.json", encoding="utf-8"
    ) as infile:
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
        r"^/?coursemedia", "courses", lecture_pdf.metadata.get("file")
    )
    assert lecture_pdf.metadata.get("learning_resource_types") == ["Lecture Notes"]

    get_valid_new_filename_mock.assert_any_call(
        website.pk,
        lecture_pdf.dirpath,
        "lec1",
        lecture_pdf.text_id,
    )

    # Any existing content not imported should be deleted
    obsolete_id = "testing123"
    WebsiteContentFactory.create(website=website, text_id=obsolete_id)
    assert WebsiteContent.objects.filter(website=website, text_id=obsolete_id).exists()
    import_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, starter_id=website_starter.id
    )
    assert not WebsiteContent.objects.filter(
        website=website, text_id=obsolete_id
    ).exists()


@mock_aws
def test_import_ocw2hugo_sitemetadata_legacy(settings, root_website):
    """Make sure we handle importing levels, term, and year in a legacy format"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    with open(  # noqa: PTH123
        f"test_ocw2hugo/{name}/data/course_legacy.json", encoding="utf-8"
    ) as course_json_file:
        course_json = json.load(course_json_file)

    level_dict = {"level": "name of level", "url": "ignore"}
    course_json["level"] = level_dict
    del course_json["year"]
    website = Website.objects.create(name=name)
    import_ocw2hugo_sitemetadata(course_json, website)
    metadata = website.websitecontent_set.get(type="sitemetadata").metadata

    assert metadata["level"] == [level_dict["level"]]
    assert metadata["term"] == course_json["term"]
    assert (
        metadata["year"] is None
    )  # this was added later but we should not break on older legacy course JSON files


@mock_aws
def test_import_ocw2hugo_course_metadata(settings, root_website):
    """import_ocw2hugo_course should also populate site metadata"""
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
            },
        },
    ]

    website = Website.objects.get(name=name)
    metadata = WebsiteContent.objects.get(website=website, type=CONTENT_TYPE_METADATA)
    assert metadata.metadata == {
        "level": ["Undergraduate"],
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
        "course_image": {
            "content": "ba36b428-9898-8e45-81d4-2067ac439546",
            "website": "1-050-engineering-mechanics-i-fall-2007",
        },
        "course_image_thumbnail": {
            "content": "4cdfb4e3-32fa-9fdf-a166-c337e35fc009",
            "website": "1-050-engineering-mechanics-i-fall-2007",
        },
        "learning_resource_types": ["Problem Sets", "Lecture Notes"],
        "term": "Fall",
        "year": "2007",
        "legacy_uid": "95f204a1-7715-8120-c7c9-66014bee40dd",
    }


@mock_aws
@pytest.mark.parametrize("gdrive_enabled", [True, False])
def test_import_ocw2hugo_course_gdrive(mocker, settings, gdrive_enabled):
    """Google drive folders should be created if integration is enabled"""
    mocker.patch("ocw_import.api.is_gdrive_enabled", return_value=gdrive_enabled)
    mock_sync_gdrive = mocker.patch(
        "ocw_import.api.create_gdrive_folders",
    )
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    if gdrive_enabled:
        mock_sync_gdrive.assert_called_once_with(website.short_id)
    else:
        mock_sync_gdrive.assert_not_called()


@mock_aws
def test_import_ocw2hugo_course_bad_date(mocker, settings):
    """Website publish date should be null if the JSON date can't be parsed"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mocker.patch("ocw_import.api.parse_date", side_effect=ValueError())
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    website = Website.objects.get(name=name)
    assert website.publish_date is None


@mock_aws
def test_import_ocw2hugo_course_noncourse(settings):
    """Website should not be created for a non-course"""
    setup_s3(settings)
    name = "biology"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).count() == 0


@mock_aws
def test_import_ocw2hugo_course_log_exception(mocker, settings):
    """Log an exception if the website cannot be saved/updated"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mocker.patch("ocw_import.api.parse_date", return_value="Invalid date")
    mock_log = mocker.patch("ocw_import.api.log.exception")
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    assert Website.objects.filter(name=name).first() is None
    mock_log.assert_called_once_with("Error saving website %s", s3_key)


@mock_aws
def test_import_ocw2hugo_content_log_exception(mocker, settings):
    """Log an exception if the website content cannot be saved/updated"""
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
    ("course_num", "term", "year", "expected_id"),
    [
        ["6.0001", "", "", "6.0001"],  # noqa: PT007
        ["5.3", "Spring", "2022", "5.3-spring-2022"],  # noqa: PT007
        ["5.3", "Spring 2022", None, "5.3-spring-2022"],  # noqa: PT007
        ["5.3", "January IAP", "2011", "5.3-january-iap-2011"],  # noqa: PT007
        [  # noqa: PT007
            "18.650 (formerly 18.443) ",
            "Spring",
            "2015",
            "18.650-spring-2015",
        ],
        [None, "January IAP", "2011", None],  # noqa: PT007
    ],
)
def test_get_short_id(course_num, term, year, expected_id):
    """get_short_id should return expected values, or raise an error if no course number"""
    metadata = {"primary_course_number": course_num, "term": term, "year": year}
    if expected_id:
        website = WebsiteFactory.create(short_id=expected_id)
        short_id = get_short_id(website.name, metadata)
        assert short_id == expected_id
        for i in range(2, 5):
            name = f"site_name_{i}"
            website.short_id = get_short_id(website.name, metadata)
            new_site = WebsiteFactory.create(
                name=name, short_id=get_short_id(name, metadata)
            )
            assert new_site.short_id == f"{expected_id}-{i}"
            assert website.short_id == expected_id
    else:
        with pytest.raises(ValueError):  # noqa: PT011
            get_short_id("random-name", metadata)


@mock_aws
def test_import_ocw2hugo_menu(settings, mocker):
    """Website publish date should be null if the JSON date can't be parsed"""
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


@mock_aws
def test_import_ocw2hugo_video_gallery(mocker, settings):
    """Website publish date should be null if the JSON date can't be parsed"""
    setup_s3(settings)
    name = "es-s41-speak-italian-with-your-mouth-full-spring-2012"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    mocker.patch("ocw_import.api.parse_date", side_effect=ValueError())
    import_ocw2hugo_course(MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key)
    video_lectures = WebsiteContent.objects.get(
        text_id="383b8d1c-30df-d781-cc05-c1c648453997"
    )
    assert video_lectures.type == "video_gallery"


@mock_aws
@pytest.mark.parametrize("website_exists", [True, False])
def test_update_ocw2hugo_course(mocker, website_exists):
    """Test update_ocw2hugo_course"""
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"
    content_field = "title"

    mock_update_ocw2hugo_content = mocker.patch(
        "ocw_import.api.update_ocw2hugo_content"
    )

    if website_exists:
        WebsiteFactory.create(name=name)

    update_ocw2hugo_course(
        MOCK_BUCKET_NAME, TEST_OCW2HUGO_PREFIX, s3_key, content_field
    )

    if website_exists:
        mock_update_ocw2hugo_content.assert_called_once()
    else:
        mock_update_ocw2hugo_content.assert_not_called()


@pytest.mark.parametrize(
    ("content_json", "resource_types"),
    [
        [  # noqa: PT007
            {
                "ocw_type": "CourseSection",
                "parent_type": "CourseSection",
                "title": "First Paper Assignment",
                "parent_title": "Lecture Summaries",
            },
            [OCW_TYPE_LECTURE_NOTES],
        ],
        [  # noqa: PT007
            {
                "ocw_type": "CourseSection",
                "title": "First Paper Assignment",
            },
            [OCW_TYPE_ASSIGNMENTS],
        ],
        [  # noqa: PT007
            {
                "ocw_type": "CourseSection",
                "parent_type": "CourseSection",
                "title": "First Paper Assignment",
                "parent_title": "Assignments and Exams",
            },
            [],
        ],
        [  # noqa: PT007
            {
                "ocw_type": "CourseSection",
                "parent_type": "CourseSection",
                "title": "First Paper Assignment",
                "parent_title": OCW_TYPE_LECTURE_NOTES,
            },
            [OCW_TYPE_LECTURE_NOTES],
        ],
        [  # noqa: PT007
            {
                "ocw_type": "CourseSection",
                "title": "Exercises",
            },
            [],
        ],
    ],
)
def test_get_learning_resource_types(content_json, resource_types):
    """Test get_learning_resource_types"""
    result = get_learning_resource_types(content_json)
    assert result == resource_types


@mock_aws
@pytest.mark.parametrize("content_exists", [True, False])
@pytest.mark.parametrize(
    "update_field",
    [
        "title",
        "metadata.description",
        "metadata.image_metadata.image-alt",
        None,
        "non_existant",
        "metadata.non_existant",
    ],
)
@pytest.mark.parametrize("create_new_content", [True, False])
def test_update_ocw2hugo_course_content(
    settings, content_exists, update_field, create_new_content
):
    """update_ocw2hugo_course_content should update website content"""
    setup_s3(settings)
    name = "1-050-engineering-mechanics-i-fall-2007"
    s3_key = f"{TEST_OCW2HUGO_PREFIX}{name}/data/course_legacy.json"

    website = WebsiteFactory.create(name=name)

    if content_exists:
        WebsiteContentFactory.create(
            website=website,
            text_id="ba36b428-9898-8e45-81d4-2067ac439546",
            title="original title",
            metadata={
                "description": "original description",
                "image_metadata": {"image-alt": "original alt"},
            },
        )

    update_ocw2hugo_course(
        MOCK_BUCKET_NAME,
        TEST_OCW2HUGO_PREFIX,
        s3_key,
        update_field,
        create_new_content=create_new_content,
    )

    if content_exists:
        resource = WebsiteContent.objects.get(
            website=website,
            text_id="ba36b428-9898-8e45-81d4-2067ac439546",
        )

        assert "non_existant" not in resource.metadata

        if update_field == "title":
            assert resource.title == "1-050f07.jpg"
            assert resource.metadata["description"] == "original description"
        elif update_field not in [None, "non_existant", "metadata.non_existant"]:
            assert resource.title == "original title"
            if update_field == "metadata.description":
                assert resource.metadata["description"].startswith(
                    "Lecture 4 explores the collapse of the"
                )
                assert (
                    resource.metadata["image_metadata"]["image-alt"] == "original alt"
                )
            else:
                assert resource.metadata["description"] == "original description"
                assert resource.metadata["image_metadata"]["image-alt"] == (
                    "Sketch of the World Trade Center towers and graph showing velocity profiles."
                )
        else:
            assert resource.title == "original title"
            assert resource.metadata["description"] == "original description"
            assert resource.metadata["image_metadata"]["image-alt"] == "original alt"
    else:
        assert WebsiteContent.objects.filter(
            website=website,
            text_id="35806cc1-1f73-e1dd-f902-580c83d1566f",
        ).count() == (1 if create_new_content else 0)


class TestUpdateContentFromS3Data:
    """
    Test that updating a single content object with s3 data only updates the
    specified fields.
    """

    @staticmethod
    def get_updated_content_and_parent(update_field):
        """Run update_content_from_s3_data with test data and return content, parent"""
        website = WebsiteFactory.build()
        content = WebsiteContentFactory.build(
            markdown="original markdown",
            metadata={"title": "original title"},
            website=website,
        )
        content.save = Mock()
        # prepare the parent, but do not set content.parent_id.
        # that's one of the things we'll test
        parent = WebsiteContentFactory.build(id=123)

        s3_content_data = {
            "markdown": "s3 markdown",
            "metadata": {
                "title": "s3 title",
                "author": "s3 author",
                "parent_uid": "s3_parent_uid",
            },
            "parent": parent,
        }
        with patch("websites.models.WebsiteContent.objects") as mock:
            mock.filter.return_value.first.return_value = content
            website = content.website
            text_id = content.text_id
            update_content_from_s3_data(website, text_id, s3_content_data, update_field)

        return content, parent

    def test_update_non_metadata_field(self):
        """
        Only content.markdown should change.
        """
        content, _ = self.get_updated_content_and_parent("markdown")
        assert content.save.call_count == 1
        assert content.markdown == "s3 markdown"
        assert content.metadata == {"title": "original title"}
        assert content.parent_id is None

    def test_update_metadata_title(self):
        """
        Only metadata.title should change, and no new metadata keys.
        """
        content, _ = self.get_updated_content_and_parent("metadata.title")
        assert content.save.call_count == 1
        assert content.markdown == "original markdown"
        assert content.metadata == {"title": "s3 title"}
        assert content.parent_id is None

    def test_update_metadata_author(self):
        """
        metadata.author should be added, no other changes.
        """
        content, _ = self.get_updated_content_and_parent("metadata.author")
        assert content.save.call_count == 1
        assert content.markdown == "original markdown"
        assert content.metadata == {
            "title": "original title",
            "author": "s3 author",
        }
        assert content.parent_id is None

    def test_update_metadata_parent_uid(self):
        """
        Test that updating metadata.parent_uid also updates parent_id FK.
        """
        content, parent = self.get_updated_content_and_parent("metadata.parent_uid")
        assert content.save.call_count == 1
        assert content.markdown == "original markdown"
        assert content.metadata == {
            "title": "original title",
            "parent_uid": "s3_parent_uid",
        }
        assert parent.id is not None
        assert content.parent_id == parent.id
