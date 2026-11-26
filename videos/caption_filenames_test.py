"""Tests for videos.caption_filenames"""

import pytest
from django.conf import settings
from django.utils.text import slugify

from gdrive_sync.factories import DriveFileFactory
from videos.caption_filenames import (
    ParsedCaptionName,
    caption_source_name,
    find_caption_files,
    find_video_for_caption,
    parse_caption_filename,
    site_languages,
    video_name_key,
)
from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
    site_config_with_resource_languages,
)

LANGS = {"en", "es", "fr", "pt"}


@pytest.mark.parametrize(
    ("name", "kind", "keys", "language", "locale"),
    [
        ("lecture-1_captions-es.vtt", "captions", ("lecture1",), "es", None),
        ("lecture-1_captions_es.vtt", "captions", ("lecture1",), "es", None),
        ("lecture-1_captions.es.vtt", "captions", ("lecture1",), "es", None),
        (
            "lecture-1_es_captions.vtt",
            "captions",
            ("lecture1es", "lecture1"),
            "es",
            None,
        ),
        ("Lecture_1-Captions-ES.vtt", "captions", ("lecture1",), "es", None),
        ("lecture-1_captions-pt-BR.vtt", "captions", ("lecture1",), "pt", "BR"),
        ("lecture-1_captions_300k.vtt", "captions", ("lecture1",), None, None),
        ("lecture-1_captions-xx.vtt", "captions", ("lecture1",), None, None),
        ("lecture-1_transcript-fr.pdf", "transcript", ("lecture1",), "fr", None),
        (
            "mit6_100lf22_lec01_es_captions.vtt",
            "captions",
            ("mit6100lf22lec01es", "mit6100lf22lec01"),
            "es",
            None,
        ),
    ],
)
def test_parse_caption_filename(name, kind, keys, language, locale):
    """Caption and transcript names are parsed into kind, video keys and language"""
    assert parse_caption_filename(name, LANGS) == ParsedCaptionName(
        kind, keys, language, locale
    )


@pytest.mark.parametrize(
    "name",
    ["lecture-1_captions-es.pdf", "lecture-1.vtt", "captions-es.vtt", "notes.pdf"],
)
def test_parse_caption_filename_no_match(name):
    """Names without a keyword, a video name or a matching extension are no match"""
    assert parse_caption_filename(name, LANGS) is None


def test_video_name_key():
    """Separators and case are normalized"""
    assert video_name_key("6.100L_Lecture (1).Version-2") == "6100llecture1version2"


@pytest.mark.django_db
def test_site_languages_reads_starter_language_options():
    """The site's languages are the option values of the resource language field"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            config=site_config_with_resource_languages("en", "es")
        )
    )
    assert site_languages(website) == frozenset({"en", "es"})


@pytest.mark.django_db
def test_site_languages_without_field_is_empty():
    """A starter without a resource language field gives no languages"""
    website = WebsiteFactory.create(starter=WebsiteStarterFactory.create())
    assert site_languages(website) == frozenset()


@pytest.mark.django_db
def test_caption_source_name_prefers_drive_name():
    """The original Drive name keeps the dots that the S3 key loses"""
    website = WebsiteFactory.create()
    resource = WebsiteContentFactory.create(
        website=website,
        filename="lecture-1_captionses_vtt",
        file=f"{website.s3_path}/lecture-1_captionses.vtt",
    )
    DriveFileFactory.create(
        website=website, resource=resource, name="lecture-1_captions.es.vtt"
    )
    assert caption_source_name(resource) == "lecture-1_captions.es.vtt"


@pytest.mark.django_db
def test_caption_source_name_strips_studio_upload_prefix():
    """Without a Drive file, the file's basename is used minus Studio's text_id prefix"""
    website = WebsiteFactory.create()
    resource = WebsiteContentFactory.create(
        website=website,
        file=(
            f"{website.s3_path}/"
            "0b6c3f2a9d1e4f5a8b7c6d5e4f3a2b1c_lecture-1_captions-es.vtt"
        ),
    )
    assert caption_source_name(resource) == "lecture-1_captions-es.vtt"


@pytest.mark.django_db
def test_caption_source_name_without_file():
    """A resource with no file and no Drive file has no name to parse"""
    resource = WebsiteContentFactory.create(file=None)
    assert caption_source_name(resource) is None


def make_video(website, filename):
    """Create a Video resource"""
    return WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        filename=filename,
        metadata={"resourcetype": RESOURCE_TYPE_VIDEO, "video_files": {}},
    )


def make_file(website, name):
    """Create a resource for an uploaded file with this name"""
    return WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        filename=name.replace(".", "_"),
        file=f"{website.s3_path}/{name}",
        metadata={"resourcetype": "Other"},
    )


@pytest.mark.django_db
def test_find_caption_files_flexible_names():
    """Captions and transcripts are found by the parsed video name, in any form"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            config=site_config_with_resource_languages("en", "es", "fr")
        )
    )
    video = make_video(website, "6100l-lecture-1-version-2_mp4")
    es_caption = make_file(website, "6100L_Lecture_1_Version_2_captions_es.vtt")
    fr_transcript = make_file(website, "6100l-lecture-1-version-2_transcript-fr.pdf")
    make_file(website, "6100l-lecture-10-version-2_captions.vtt")
    make_file(website, "6100l-lecture-1-version-2_notes.pdf")

    assert find_caption_files(video) == ([es_caption], [fr_transcript])


@pytest.mark.django_db
def test_find_caption_files_extensionless_video_ignores_course_file():
    """A file named after a cut-down video name is not the video's own file"""
    website = WebsiteFactory.create()
    lec3 = make_video(website, "mitesd_932s06_lec03")
    own_caption = make_file(website, "mitesd_932s06_lec03_captions.vtt")
    make_file(website, "mitesd_932s06_captions.vtt")

    assert find_caption_files(lec3) == ([own_caption], [])


@pytest.mark.django_db
def test_find_video_for_caption_prefers_longer_video_name():
    """A code before the keyword stays part of the video name when that video exists"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            config=site_config_with_resource_languages("en", "es")
        )
    )
    lecture = make_video(website, "lecture_mp4")
    lecture_es = make_video(website, "lecture-es_mp4")
    caption = make_file(website, "lecture_es_captions.vtt")

    assert find_video_for_caption(caption) == (
        lecture_es,
        settings.YT_FIELD_CAPTIONS_RESOURCES,
    )
    assert find_caption_files(lecture_es) == ([caption], [])
    assert find_caption_files(lecture) == ([], [])


@pytest.mark.django_db
def test_find_video_for_caption_language_before_keyword():
    """Without a video named after the code, the code is the file's language"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            config=site_config_with_resource_languages("en", "es")
        )
    )
    lecture = make_video(website, "lecture_mp4")
    caption = make_file(website, "lecture_es_captions.vtt")
    transcript = make_file(website, "Lecture-ES-Transcript.pdf")

    assert find_video_for_caption(caption) == (
        lecture,
        settings.YT_FIELD_CAPTIONS_RESOURCES,
    )
    assert find_video_for_caption(transcript) == (
        lecture,
        settings.YT_FIELD_TRANSCRIPT_RESOURCES,
    )
    assert find_caption_files(lecture) == ([caption], [transcript])


@pytest.mark.django_db
def test_find_video_for_caption_no_match():
    """A file whose name matches no Video resource has no video"""
    website = WebsiteFactory.create()
    make_video(website, "lecture-1_mp4")
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        filename="orphan_mp4",
        metadata={"resourcetype": "Other"},
    )

    assert find_video_for_caption(make_file(website, "orphan_captions.vtt")) is None
    assert find_video_for_caption(make_file(website, "lecture-1.vtt")) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("drive_video_name", "caption_name"),
    [
        ("6.100L Lecture 1.mp4", "6.100L Lecture 1_captions.vtt"),
        ("Lecture (1).mp4", "Lecture (1)_captions-es.vtt"),
        ("Lecture's & Notes.mp4", "Lecture's & Notes captions.vtt"),
        ("lecture1.mp4", "lecture1_captions(1).vtt"),
    ],
)
def test_caption_links_to_video_with_punctuated_drive_name(
    drive_video_name, caption_name
):
    """Drive slugs drop punctuation from the video name, the caption name keeps it"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            config=site_config_with_resource_languages("en", "es")
        )
    )
    stem, extension = drive_video_name.rsplit(".", 1)
    video = make_video(website, f"{slugify(stem, allow_unicode=True)}_{extension}")
    caption = make_file(website, caption_name)

    assert find_caption_files(video) == ([caption], [])
    assert find_video_for_caption(caption) == (
        video,
        settings.YT_FIELD_CAPTIONS_RESOURCES,
    )
