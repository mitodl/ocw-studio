"""Tests for the backfill_orphaned_caption_transcript_files management command"""  # noqa: INP001

import importlib
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from moto import mock_aws

from main.s3_utils import get_boto3_resource
from videos.conftest import MOCK_BUCKET_NAME, setup_s3
from websites.constants import CONTENT_FILENAME_MAX_LEN, CONTENT_TITLE_MAX_LEN
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent

pytestmark = pytest.mark.django_db


class TransientS3Error(Exception):
    """Simulates a transient S3 failure (e.g. throttling) mid-run."""


@pytest.fixture
def mock_s3(settings):
    """Provide a moto-backed S3 bucket, matching the repo's setup_s3 convention."""
    with mock_aws():
        setup_s3(settings)
        settings.AWS_STORAGE_BUCKET_NAME = MOCK_BUCKET_NAME
        yield get_boto3_resource("s3").Bucket(MOCK_BUCKET_NAME)


def _run(**kwargs):
    """Invoke the command, returning captured stdout."""
    out = StringIO()
    call_command("backfill_orphaned_caption_transcript_files", stdout=out, **kwargs)
    return out.getvalue()


def test_removes_empty_string_leftovers(mock_s3):
    """Empty-string _file values are removed with no resource created."""
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

    _run()

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf
    assert "video_captions_resources" not in vf
    assert "video_transcript_resources" not in vf


def test_creates_resource_for_existing_s3_object(mock_s3):
    """A real orphan path with an existing S3 object gets a new resource created."""
    website = WebsiteFactory.create()
    caption_key = f"courses/{website.name}/1AbCdEf_transcript.webvtt"
    mock_s3.put_object(Key=caption_key, Body=b"WEBVTT")

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

    _run()

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    resources = vf["video_captions_resources"]
    assert resources["website"] == website.name
    assert len(resources["content"]) == 1

    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert created.filename == "lecture1_mp4_captions"
    assert created.dirpath == "content/resources"
    assert created.file.name == caption_key
    assert created.metadata["resourcetype"] == "Other"
    assert created.metadata["file"] == f"/{caption_key}"


def test_skips_missing_s3_object(mock_s3):
    """A real orphan path whose S3 object no longer exists is left untouched."""
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

    output = _run()

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert vf["video_transcript_file"] == transcript_path
    assert "video_transcript_resources" not in vf
    assert "Skipping missing S3 object" in output


def test_appends_to_existing_resources(mock_s3):
    """A backfilled resource is appended to an existing _resources content list."""
    website = WebsiteFactory.create()
    fr_caption = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_captions_fr_vtt",
        file=f"courses/{website.name}/lecture1_captions_fr.vtt",
    )
    en_key = f"courses/{website.name}/1EnglishId_transcript.webvtt"
    mock_s3.put_object(Key=en_key, Body=b"WEBVTT")

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

    _run()

    video.refresh_from_db()
    content = video.metadata["video_files"]["video_captions_resources"]["content"]
    assert str(fr_caption.text_id) in content
    assert len(content) == 2


def test_appends_to_existing_scalar_string_content(mock_s3):
    """A legacy scalar-string _resources.content value is preserved, not dropped."""
    website = WebsiteFactory.create()
    fr_caption = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_captions_fr_vtt",
        file=f"courses/{website.name}/lecture1_captions_fr.vtt",
    )
    en_key = f"courses/{website.name}/1EnglishId_transcript.webvtt"
    mock_s3.put_object(Key=en_key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"/{en_key}",
                "video_captions_resources": {
                    "content": str(fr_caption.text_id),
                    "website": website.name,
                },
            },
        },
    )

    _run()

    video.refresh_from_db()
    content = video.metadata["video_files"]["video_captions_resources"]["content"]
    assert isinstance(content, list)
    assert str(fr_caption.text_id) in content
    assert len(content) == 2


def test_reuses_existing_resource_for_same_s3_key(mock_s3):
    """An orphan path matching an already-created resource is linked, not duplicated."""
    website = WebsiteFactory.create()
    key = f"courses/{website.name}/1AbCdEf_transcript.webvtt"
    already_linked = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4_captions",
        file=key,
    )

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{key}"},
        },
    )

    _run()

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    resources = vf["video_captions_resources"]
    assert resources["content"] == [str(already_linked.text_id)]

    assert WebsiteContent.objects.filter(website=website, file=key).count() == 1


def test_reusing_resources_costs_one_query_per_resource(mock_s3):
    """Reusing an existing resource costs one query per resource, not two.

    Regression test: the reused-resource lookup has no select_related, so
    reading its website through it (`resource.website.name`) costs an extra
    query per resource on top of the lookup itself, unlike reading the
    website through the already select_related video (`content.website.name`).
    A second reused resource should add exactly one query (its own lookup),
    not two.
    """

    def _reused_resource_query_count(website, video_count):
        for i in range(video_count):
            key = f"courses/{website.name}/{i}_transcript.webvtt"
            WebsiteContentFactory.create(
                website=website, filename=f"l{i}_captions", file=key
            )
            WebsiteContentFactory.create(
                website=website,
                filename=f"lecture{i}_mp4",
                dirpath="content/resources",
                metadata={
                    "resourcetype": "Video",
                    "video_files": {"video_captions_file": f"/{key}"},
                },
            )
        with CaptureQueriesContext(connection) as ctx:
            _run(filter=website.name)
        return len(ctx.captured_queries)

    one_video_queries = _reused_resource_query_count(WebsiteFactory.create(), 1)
    two_video_queries = _reused_resource_query_count(WebsiteFactory.create(), 2)

    assert two_video_queries - one_video_queries == 1


def test_partial_progress_persists_on_mid_run_failure(mock_s3, monkeypatch):
    """A crash partway through only loses the current unflushed batch.

    Regression test for periodic batch flushing: rows already flushed before
    a transient failure (e.g. an S3 throttling error) stay persisted, so a
    retry only has to redo the unflushed remainder, not the whole run.
    """
    cmd_module = importlib.import_module(
        "websites.management.commands.backfill_orphaned_caption_transcript_files"
    )
    monkeypatch.setattr(cmd_module, "_BULK_UPDATE_BATCH_SIZE", 1)

    website = WebsiteFactory.create()
    videos = []
    for i in range(3):
        key = f"courses/{website.name}/{i}_transcript.webvtt"
        mock_s3.put_object(Key=key, Body=b"WEBVTT")
        video = WebsiteContentFactory.create(
            website=website,
            filename=f"lecture{i}_mp4",
            dirpath="content/resources",
            metadata={
                "resourcetype": "Video",
                "video_files": {"video_captions_file": f"/{key}"},
            },
        )
        videos.append(video)

    original_check = cmd_module._object_exists_in_s3  # noqa: SLF001
    call_count = 0

    def _fail_on_third_call(s3, bucket_name, key):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise TransientS3Error
        return original_check(s3, bucket_name, key)

    monkeypatch.setattr(cmd_module, "_object_exists_in_s3", _fail_on_third_call)

    with pytest.raises(TransientS3Error):
        _run(filter=website.name)

    for video in videos:
        video.refresh_from_db()
    processed_count = sum(
        1
        for video in videos
        if "video_captions_file" not in video.metadata["video_files"]
    )
    assert processed_count == 2


def test_deduplicates_filename_collision(mock_s3):
    """Filename collisions in the same (website, dirpath) get a numeric suffix."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, filename="lecture1_mp4_captions", dirpath="content/resources"
    )
    key = f"courses/{website.name}/1AbC_transcript.webvtt"
    mock_s3.put_object(Key=key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{key}"},
        },
    )

    _run()

    video.refresh_from_db()
    resources = video.metadata["video_files"]["video_captions_resources"]
    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert created.filename == "lecture1_mp4_captions2"


def test_skips_non_video_content(mock_s3):
    """Content without resourcetype=Video is not modified even if it has video_files."""
    content = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Document",
            "video_files": {"video_captions_file": ""},
        }
    )

    _run()

    content.refresh_from_db()
    # Non-video content is untouched because the queryset filters to resourcetype=Video
    assert "video_captions_file" in content.metadata["video_files"]


def test_backfills_both_captions_and_transcript_for_same_video(mock_s3):
    """A video with both orphaned fields gets both backfilled in the same run."""
    website = WebsiteFactory.create()
    captions_key = f"courses/{website.name}/1Caption_transcript.webvtt"
    transcript_key = f"courses/{website.name}/1Transcript_transcript.pdf"
    mock_s3.put_object(Key=captions_key, Body=b"WEBVTT")
    mock_s3.put_object(Key=transcript_key, Body=b"%PDF")

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

    _run()

    video.refresh_from_db()
    vf = video.metadata["video_files"]
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf

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


def test_filter_by_website(mock_s3):
    """--filter restricts the backfill to the named website(s)."""
    included = WebsiteFactory.create()
    excluded = WebsiteFactory.create()
    for website in (included, excluded):
        WebsiteContentFactory.create(
            website=website,
            filename="lecture1_mp4",
            metadata={
                "resourcetype": "Video",
                "video_files": {"video_captions_file": ""},
            },
        )

    _run(filter=included.name)

    included_video = WebsiteContent.objects.get(
        website=included, filename="lecture1_mp4"
    )
    excluded_video = WebsiteContent.objects.get(
        website=excluded, filename="lecture1_mp4"
    )
    assert "video_captions_file" not in included_video.metadata["video_files"]
    assert "video_captions_file" in excluded_video.metadata["video_files"]


def test_truncates_long_video_filename_to_fit_length_limit(mock_s3):
    """
    A video filename already at the length limit must not produce a
    too-long filename when suffixed with _captions/_transcript (the actual
    staging DataError this command was written to fix).
    """
    website = WebsiteFactory.create()
    long_filename = "a" * CONTENT_FILENAME_MAX_LEN
    key = f"courses/{website.name}/1AbCdEf_transcript.webvtt"
    mock_s3.put_object(Key=key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename=long_filename,
        dirpath="content/resources",
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{key}"},
        },
    )

    _run()

    video.refresh_from_db()
    resources = video.metadata["video_files"]["video_captions_resources"]
    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert len(created.filename) <= CONTENT_FILENAME_MAX_LEN
    assert created.filename.endswith("_captions")


def test_truncates_long_video_title_to_fit_length_limit(mock_s3):
    """
    A video title already at the length limit must not produce a too-long
    title when suffixed with captions/transcript.
    """
    website = WebsiteFactory.create()
    long_title = "a" * CONTENT_TITLE_MAX_LEN
    key = f"courses/{website.name}/1AbCdEf_transcript.webvtt"
    mock_s3.put_object(Key=key, Body=b"WEBVTT")

    video = WebsiteContentFactory.create(
        website=website,
        filename="lecture1_mp4",
        dirpath="content/resources",
        title=long_title,
        metadata={
            "resourcetype": "Video",
            "video_files": {"video_captions_file": f"/{key}"},
        },
    )

    _run()

    video.refresh_from_db()
    resources = video.metadata["video_files"]["video_captions_resources"]
    created = WebsiteContent.objects.get(text_id=resources["content"][0])
    assert len(created.title) <= CONTENT_TITLE_MAX_LEN
    assert created.title.endswith(" captions")
