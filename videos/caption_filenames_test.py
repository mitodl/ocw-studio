"""Tests for videos.caption_filenames"""

from copy import deepcopy

import pytest

from gdrive_sync.factories import DriveFileFactory
from videos.caption_filenames import (
    ParsedCaptionName,
    caption_source_name,
    parse_caption_filename,
    site_languages,
    video_name_key,
)
from websites.constants import CONTENT_TYPE_RESOURCE
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)

LANGS = {"en", "es", "fr", "pt"}


def starter_with_languages(*codes):
    """Return a starter whose resource item has a language select with these codes"""
    starter = WebsiteStarterFactory.create()
    config = deepcopy(starter.config)
    resource_item = next(
        item for item in config["collections"] if item["name"] == CONTENT_TYPE_RESOURCE
    )
    resource_item["fields"].append(
        {
            "label": "Language",
            "name": "language",
            "widget": "select",
            "options": [{"label": code.upper(), "value": code} for code in codes],
        }
    )
    starter.config = config
    starter.save()
    return starter


@pytest.mark.parametrize(
    ("name", "kind", "keys", "language", "locale"),
    [
        ("lecture-1_captions-es.vtt", "captions", ("lecture-1",), "es", None),
        ("lecture-1_captions_es.vtt", "captions", ("lecture-1",), "es", None),
        ("lecture-1_captions.es.vtt", "captions", ("lecture-1",), "es", None),
        (
            "lecture-1_es_captions.vtt",
            "captions",
            ("lecture-1-es", "lecture-1"),
            "es",
            None,
        ),
        ("Lecture_1-Captions-ES.vtt", "captions", ("lecture-1",), "es", None),
        ("lecture-1_captions-pt-BR.vtt", "captions", ("lecture-1",), "pt", "BR"),
        ("lecture-1_captions_300k.vtt", "captions", ("lecture-1",), None, None),
        ("lecture-1_captions-xx.vtt", "captions", ("lecture-1",), None, None),
        ("lecture-1_transcript-fr.pdf", "transcript", ("lecture-1",), "fr", None),
        (
            "mit6_100lf22_lec01_es_captions.vtt",
            "captions",
            ("mit6-100lf22-lec01-es", "mit6-100lf22-lec01"),
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
    assert video_name_key("6100L_Lecture 1.Version-2") == "6100l-lecture-1-version-2"


@pytest.mark.django_db
def test_site_languages_reads_starter_language_options():
    """The site's languages are the option values of the resource language field"""
    website = WebsiteFactory.create(starter=starter_with_languages("en", "es"))
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
