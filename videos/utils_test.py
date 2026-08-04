"""Tests for videos.utils"""

from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from videos.utils import (
    clean_uuid_filename,
    create_new_content,
    generate_s3_path,
    get_content_dirpath,
    get_tags_with_course,
    parse_caption_language_locale,
    resolve_language_locale,
    update_metadata,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)

# pylint:disable=redefined-outer-name
pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("use_content", [True, False])
@pytest.mark.parametrize(
    ("file_extension", "expected_postfix"),
    [("vtt", "_captions"), ("webvtt", "_captions"), ("pdf", "_transcript")],
)
def test_generate_s3_path(use_content, file_extension, expected_postfix):
    """Test generate_s3_path generates appropriate paths for captions."""

    website = WebsiteFactory.create()
    filename = str(uuid4())
    file = SimpleUploadedFile(
        f"/courses/{website.name}/{filename}-file.{file_extension}", b"Nothing here."
    )
    expected_new_path = f"{website.s3_path.strip('/')}/{filename}-file{expected_postfix}.{file_extension}"

    if use_content:
        file_or_content = WebsiteContentFactory.create(website=website, file=file)
    else:
        file_or_content = file

    new_path = generate_s3_path(file_or_content, website)

    assert new_path == expected_new_path


@pytest.mark.parametrize(
    ("filename", "expected_result"),
    [
        (f"{uuid4()}_file.ext", "file.ext"),
        ("file.ext", "file.ext"),
    ],
)
def test_clean_uuid_filename(filename, expected_result):
    """Test clean_uuid_filename strips uuid from filename"""
    assert clean_uuid_filename(filename) == expected_result


def test_get_content_dirpath():
    """Test get_content_dirpath returns the folder of the collection_type"""
    starter = WebsiteStarterFactory.create()

    dirpath = get_content_dirpath(starter.slug, "resource")

    assert dirpath == "content/resource"


def test_create_new_content(mocker):
    """Test that create_new_content creates or updates the resource correctly."""
    source_course = WebsiteFactory.create()
    destination_course = WebsiteFactory.create()
    source_content = WebsiteContentFactory.create(
        website=source_course, file="source_file"
    )

    mock_copy_obj_s3 = mocker.patch(
        "videos.utils.copy_obj_s3", return_value="new_s3_loc"
    )
    mock_get_dirpath_and_filename = mocker.patch(
        "videos.utils.get_dirpath_and_filename",
        return_value=["new_dirpath", "new_filename"],
    )
    mock_uuid_string = mocker.patch("videos.utils.uuid_string", return_value="new-uuid")
    new_content = create_new_content(source_content, destination_course)

    assert new_content.website == destination_course
    assert new_content.title == source_content.title
    assert new_content.type == source_content.type
    assert new_content.text_id == "new-uuid"
    expected_metadata = update_metadata(source_content, "new-uuid", "new_s3_loc")
    assert new_content.metadata == expected_metadata
    assert new_content.file.name == "new_s3_loc"
    assert new_content.dirpath == "content/resources"
    assert new_content.filename == "new_filename"

    mock_copy_obj_s3.assert_called_once_with(source_content, destination_course)
    mock_get_dirpath_and_filename.assert_called_once_with("new_s3_loc")
    mock_uuid_string.assert_called_once()


def test_get_tags_with_course_string_tags():
    """Test getting tags with course name from string tags."""
    metadata = {"video_metadata": {"video_tags": "Calculus, MATHEMATICS"}}
    course_name = "18-01-fall-2020"

    result = get_tags_with_course(metadata, course_name)

    # Tags should be lowercased, and sorted alphabetically
    assert result == "18-01-fall-2020, calculus, mathematics"
    # Original metadata should not be modified
    assert metadata["video_metadata"]["video_tags"] == "Calculus, MATHEMATICS"


def test_get_tags_with_course_no_existing_tags():
    """Test getting tags when no existing tags."""
    metadata = {"video_metadata": {}}
    course_name = "course-123"

    result = get_tags_with_course(metadata, course_name)

    # Course slug should be added
    assert result == "course-123"


def test_get_tags_with_course_already_exists():
    """Test getting tags when course name already in tags."""
    metadata = {"video_metadata": {"video_tags": "Python, MY-COURSE, Django"}}
    course_name = "my-course"

    result = get_tags_with_course(metadata, course_name)

    # Duplicates removed case-insensitively, and sorted alphabetically
    assert result == "django, my-course, python"
    # Original metadata should not be modified
    assert metadata["video_metadata"]["video_tags"] == "Python, MY-COURSE, Django"


def test_get_tags_with_course_empty_string():
    """Test getting tags with empty string."""
    metadata = {"video_metadata": {"video_tags": ""}}
    course_name = "new-course"

    result = get_tags_with_course(metadata, course_name)

    # Course slug added
    assert result == "new-course"


def test_get_tags_with_course_mixed_case_duplicates():
    """Test that mixed case duplicates are handled correctly."""
    metadata = {"video_metadata": {"video_tags": "Python, python, PYTHON, django"}}
    course_name = "my-course"

    result = get_tags_with_course(metadata, course_name)

    # Duplicates should be removed (case-insensitive), sorted
    assert result == "django, my-course, python"


def test_get_tags_with_course_whitespace_handling():
    """Test that whitespace in tags is properly stripped."""
    metadata = {"video_metadata": {"video_tags": "  Python  ,  Django  ,  AI  "}}
    course_name = "  my-course  "

    result = get_tags_with_course(metadata, course_name)

    # Whitespace stripped from tags, then sorted
    assert result == "ai, django, my-course, python"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        # Legacy convention without a language suffix — defaults to English
        ("lecture1_captions_vtt", ("en", None)),
        ("lecture1_transcript_pdf", ("en", None)),
        # GDrive pattern: <base>_captions-<lang>-<locale>.<ext> (slugified) —
        # locale returned uppercase
        ("lecture1_captions-en-us_vtt", ("en", "US")),
        ("lecture1_captions-fr-ca_vtt", ("fr", "CA")),
        ("lecture1_captions-zh-cn_webvtt", ("zh", "CN")),
        ("lecture1_captions-es-mx_srt", ("es", "MX")),
        ("lecture1_transcript-en-us_pdf", ("en", "US")),
        ("lecture1_transcript-fr-gb_pdf", ("fr", "GB")),
        # Longer filename still parsed correctly
        ("my_long_course_lecture_03_captions-pt-br_vtt", ("pt", "BR")),
        # Language-only suffix, no locale — locale group is optional
        ("lecture1_captions-fr_vtt", ("fr", None)),
        # No recognised suffix -> defaults to English, no locale
        ("some_random_file_pdf", ("en", None)),
        ("lecture1_vtt", ("en", None)),
    ],
)
def test_parse_caption_language_locale(filename, expected):
    """parse_caption_language_locale returns (language, locale) from slugified filename."""
    assert parse_caption_language_locale(filename) == expected


@pytest.mark.parametrize(
    ("metadata", "file_name", "expected"),
    [
        # explicit metadata wins over the filename
        ({"language": "es"}, "courses/s/l1_captions-fr.vtt", ("es", None)),
        # explicit language with no locale does not inherit the parsed region
        ({"language": "es"}, "courses/s/l1_captions-fr-CA.vtt", ("es", None)),
        # explicit locale wins while language still comes from the filename
        ({"locale": "BR"}, "courses/s/l1_captions-pt.vtt", ("pt", "BR")),
        ({"locale": "BR"}, "courses/s/l1_captions-pt-PT.vtt", ("pt", "BR")),
        # both explicit
        ({"language": "pt", "locale": "BR"}, "courses/s/l1_captions.vtt", ("pt", "BR")),
        # no metadata: parsed from the filename
        ({}, "courses/s/l1_captions-fr.vtt", ("fr", None)),
        ({}, "courses/s/l1_captions-en-US.vtt", ("en", "US")),
        # no metadata and no language suffix: the "en" default
        ({}, "courses/s/l1_captions.vtt", ("en", None)),
        # empty-string metadata is treated as unset, not as a language
        ({"language": "", "locale": ""}, "courses/s/l1_captions-fr.vtt", ("fr", None)),
        # explicit codes are normalized to match what the filename parse yields
        ({"language": "EN"}, "courses/s/l1_captions-fr.vtt", ("en", None)),
        ({"language": "pt", "locale": "br"}, "courses/s/l1_captions.vtt", ("pt", "BR")),
        # unusable values are unset, never a crash and never published as-is
        ({"language": "   "}, "courses/s/l1_captions-fr.vtt", ("fr", None)),
        ({"language": 5}, "courses/s/l1_captions-fr.vtt", ("fr", None)),
        ({"language": ["fr"]}, "courses/s/l1_captions-fr.vtt", ("fr", None)),
    ],
)
def test_resolve_language_locale(metadata, file_name, expected):
    """Explicit metadata wins, otherwise the filename is parsed, otherwise 'en'."""
    resource = WebsiteContentFactory.build(metadata=metadata, file=file_name)
    assert resolve_language_locale(resource) == expected


def test_resolve_language_locale_without_file():
    """A resource with no uploaded file falls back to the 'en' default."""
    resource = WebsiteContentFactory.build(metadata={}, file=None)
    assert resolve_language_locale(resource) == ("en", None)


@pytest.mark.parametrize("metadata", [None, "en", ["en"], 42])
def test_resolve_language_locale_non_dict_metadata(metadata):
    """Metadata that is not a dict is treated as absent rather than raising."""
    resource = WebsiteContentFactory.build(
        metadata=metadata, file="courses/s/l1_captions-fr.vtt"
    )
    assert resolve_language_locale(resource) == ("fr", None)
