"""Tests for website migration 0076 -- backfill orphaned caption/transcript files"""

import importlib

import pytest
from django.apps import apps
from moto import mock_aws

from main.s3_utils import get_boto3_resource
from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def migration_module():
    """Import the migration module (names with leading digits need importlib)."""
    return importlib.import_module(
        "websites.migrations.0076_backfill_orphaned_caption_transcript_files"
    )


def _setup_s3_bucket(settings):
    """Create a mocked S3 bucket for the test.

    Must be called from inside a function decorated with @mock_aws (not from
    a pytest fixture) -- get_boto3_options() injects a hardcoded minio
    endpoint_url whenever ENVIRONMENT == "dev" (the default in this repo's
    .env), which bypasses moto's interception if the settings mutation and
    S3 calls happen outside the mock context. This matches the pattern used
    by videos/conftest.py's setup_s3() and gdrive_sync/utils_test.py.
    """
    settings.ENVIRONMENT = "test"
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"  # noqa: S105
    settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
    conn = get_boto3_resource("s3")
    conn.create_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
    return conn.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)


@mock_aws
def test_migration_0076_removes_empty_string_leftovers(migration_module, settings):
    """Empty-string _file values are removed with no resource created."""
    _setup_s3_bucket(settings)
    video = WebsiteContentFactory.create(
        filename="lecture1_mp4",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": "",
                "video_transcript_file": "",
            },
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf
    assert "video_captions_resources" not in vf
    assert "video_transcript_resources" not in vf


@mock_aws
def test_migration_0076_creates_resource_for_existing_s3_object(
    migration_module, settings
):
    """A real orphan path with an existing S3 object gets a new resource created."""
    s3_bucket = _setup_s3_bucket(settings)
    website = WebsiteFactory.create()
    caption_key = f"courses/{website.name}/1AbCdEf_transcript.webvtt"
    s3_bucket.put_object(Key=caption_key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        title="Lecture 1",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{caption_key}"},
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    resources = vf["video_captions_resources"]
    assert resources["website"] == website.name
    assert len(resources["content"]) == 1

    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert created.filename == "lecture1_mp4_captions"
    assert created.dirpath == "content/resources"
    assert created.file.name == caption_key
    assert created.metadata["resourcetype"] == "Other"
    assert created.metadata["file"] == f"/{caption_key}"


@mock_aws
def test_migration_0076_skips_missing_s3_object(migration_module, settings, capsys):
    """A real orphan path whose S3 object no longer exists is left untouched."""
    _setup_s3_bucket(settings)
    website = WebsiteFactory.create()
    transcript_path = f"/courses/{website.name}/1Missing_transcript.pdf"

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_transcript_file": transcript_path},
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert vf["video_transcript_file"] == transcript_path
    assert "video_transcript_resources" not in vf
    assert "Skipping missing S3 object" in capsys.readouterr().out


@mock_aws
def test_migration_0076_appends_to_existing_resources(migration_module, settings):
    """A backfilled resource is appended to an existing _resources content list."""
    s3_bucket = _setup_s3_bucket(settings)
    website = WebsiteFactory.create()
    fr_caption = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_captions_fr_vtt",
        file=f"courses/{website.name}/lecture1_captions_fr.vtt",
    )
    en_key = f"courses/{website.name}/1EnglishId_transcript.webvtt"
    s3_bucket.put_object(Key=en_key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"/{en_key}",
                "video_captions_resources": {
                    "content": [str(fr_caption.text_id)],
                    "website": website.name,
                },
            },
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    content = video.metadata["video_files"]["video_captions_resources"]["content"]
    assert str(fr_caption.text_id) in content
    assert len(content) == 2


@mock_aws
def test_migration_0076_deduplicates_filename_collision(migration_module, settings):
    """Filename collisions in the same (website, dirpath) get a numeric suffix."""
    s3_bucket = _setup_s3_bucket(settings)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, filename="lecture1_mp4_captions", dirpath="content/resources"
    )
    key = f"courses/{website.name}/1AbC_transcript.webvtt"
    s3_bucket.put_object(Key=key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{key}"},
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    resources = video.metadata["video_files"]["video_captions_resources"]
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert created.filename == "lecture1_mp4_captions_2"


def test_migration_0076_skips_non_video_content(migration_module):
    """Content without resourcetype=Video is not modified even if it has video_files."""
    content = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Document",
            "video_files": {"video_captions_file": ""},
        }
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    content.refresh_from_db()
    # Non-video content is untouched because the queryset filters to resourcetype=Video
    assert "video_captions_file" in content.metadata["video_files"]


@mock_aws
def test_migration_0076_backfills_both_captions_and_transcript_for_same_video(
    migration_module, settings
):
    """A video with both orphaned fields gets both backfilled in the same run."""
    s3_bucket = _setup_s3_bucket(settings)
    website = WebsiteFactory.create()
    captions_key = f"courses/{website.name}/1Caption_transcript.webvtt"
    transcript_key = f"courses/{website.name}/1Transcript_transcript.pdf"
    s3_bucket.put_object(Key=captions_key, Body=b"WEBVTT")
    s3_bucket.put_object(Key=transcript_key, Body=b"%PDF")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"/{captions_key}",
                "video_transcript_file": f"/{transcript_key}",
            },
        },
    )

    migration_module._backfill_orphaned_files(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf

    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    captions_resource = WebsiteContent.objects.get(
        text_id=vf["video_captions_resources"]["content"][0]
    )
    transcript_resource = WebsiteContent.objects.get(
        text_id=vf["video_transcript_resources"]["content"][0]
    )
    assert captions_resource.filename == "lecture1_mp4_captions"
    assert transcript_resource.filename == "lecture1_mp4_transcript"
    assert captions_resource.metadata["resourcetype"] == "Other"
    assert transcript_resource.metadata["resourcetype"] == "Document"
