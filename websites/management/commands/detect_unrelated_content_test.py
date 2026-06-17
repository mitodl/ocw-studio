"""
Tests for the detect_unrelated_content management command.

The command compares the set of object keys present in S3 (under each website's
``s3_path``) against the set of files referenced by that website's
``WebsiteContent`` rows, and reports (or, with ``--delete``, removes) any S3 key
that is not backed by content.

These tests drive the command through ``call_command`` against a moto-backed S3
bucket (``@mock_aws`` + the shared ``setup_s3`` helper, matching the repo
convention). The tests at the bottom are regression tests for deletion-safety
hardening: metadata-stored file paths, soft-deleted content, and the S3
prefix-collision fix.
"""  # noqa: INP001

import json
import re
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from moto import mock_aws

from main.s3_utils import get_boto3_resource
from videos.conftest import MOCK_BUCKET_NAME, setup_s3
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.detect_unrelated_content import list_all_s3_keys

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_s3(settings):
    """Provide a moto-backed S3 bucket (the repo's @mock_aws + setup_s3 convention).

    Yields a namespace with ``put(keys)`` to add zero-byte objects and
    ``current()`` to read back the bucket's current key set. Real boto3 calls
    made by the command run against moto, so list/delete (and prefix matching)
    use genuine S3 semantics rather than a re-implementation.
    """
    with mock_aws():
        setup_s3(settings)  # fake creds + create MOCK_BUCKET_NAME
        settings.AWS_STORAGE_BUCKET_NAME = MOCK_BUCKET_NAME
        bucket = get_boto3_resource("s3").Bucket(MOCK_BUCKET_NAME)

        def put(keys):
            for key in keys:
                bucket.put_object(Key=key, Body=b"")

        def current():
            return {obj.key for obj in bucket.objects.all()}

        yield SimpleNamespace(put=put, current=current)


def _run(**kwargs):
    """Invoke the command, returning captured stdout."""
    out = StringIO()
    call_command("detect_unrelated_content", stdout=out, **kwargs)
    return out.getvalue()


def _tempfile_path(output):
    """Extract the temp-file path the command reports for large result sets."""
    match = re.search(r"temporary file located at:\s*(\S+\.json)", output)
    return Path(match.group(1)) if match else None


def test_no_unrelated_content_reports_clean(mock_s3):
    """When every S3 key is backed by content, nothing is flagged or deleted."""
    website = WebsiteFactory.create(name="clean-site", short_id="clean-site")
    related = f"{website.s3_path}/keep_doc.pdf"
    WebsiteContentFactory.create(
        website=website, type="resource", file=related, metadata={}
    )
    mock_s3.put({related})

    output = _run(filter="clean-site", delete=True)

    assert "No unrelated content found" in output
    assert related in mock_s3.current()


def test_detect_reports_unrelated_without_deleting(mock_s3):
    """Default (no --delete) run reports unrelated keys but deletes nothing."""
    website = WebsiteFactory.create(name="detect-site", short_id="detect-site")
    related = f"{website.s3_path}/keep_doc.pdf"
    orphan = f"{website.s3_path}/remove_me.bin"
    WebsiteContentFactory.create(
        website=website, type="resource", file=related, metadata={}
    )
    mock_s3.put({related, orphan})

    output = _run(filter="detect-site")

    assert "Unrelated content found" in output
    assert orphan in output
    assert related not in output
    assert orphan in mock_s3.current()  # nothing removed in detect mode


def test_delete_removes_only_unrelated_keys(mock_s3):
    """--delete removes orphaned keys and leaves referenced files intact."""
    website = WebsiteFactory.create(name="delete-site", short_id="delete-site")
    related = f"{website.s3_path}/keep.pdf"
    orphan = f"{website.s3_path}/junk.bin"
    WebsiteContentFactory.create(
        website=website, type="resource", file=related, metadata={}
    )
    mock_s3.put({related, orphan})

    output = _run(filter="delete-site", delete=True)

    remaining = mock_s3.current()
    assert orphan not in remaining
    assert related in remaining
    assert "Deleted 1 unrelated files" in output


def test_leading_slash_in_file_is_normalized(mock_s3):
    """A content file stored with a leading slash still matches its S3 key."""
    website = WebsiteFactory.create(name="slash-site", short_id="slash-site")
    key = f"{website.s3_path}/doc.pdf"
    WebsiteContentFactory.create(
        website=website, type="resource", file=f"/{key}", metadata={}
    )
    mock_s3.put({key})

    output = _run(filter="slash-site", delete=True)

    assert "No unrelated content found" in output
    assert key in mock_s3.current()  # not treated as unrelated, not deleted


def test_video_metadata_files_are_treated_as_related(mock_s3):
    """video_files metadata protects thumbnails/captions/transcripts.

    Covers the three normalization branches in _filter_unrelated_files:
    a full path already under s3_path is kept as-is, a bare filename is
    re-rooted under s3_path, and an http(s) value is ignored.
    """
    website = WebsiteFactory.create(name="video-site", short_id="video-site")
    video_file = f"{website.s3_path}/vid_video.mp4"
    thumb = f"{website.s3_path}/thumb.jpg"
    captions_key = f"{website.s3_path}/captions.vtt"
    orphan = f"{website.s3_path}/orphan.bin"
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=video_file,
        metadata={
            "video_files": {
                "video_thumbnail_file": thumb,  # full path -> kept as-is
                "video_captions_file": "captions.vtt",  # bare name -> re-rooted
                "video_transcript_file": "https://youtu.be/x",  # http -> ignored
            }
        },
    )
    mock_s3.put({video_file, thumb, captions_key, orphan})

    output = _run(filter="video-site")

    assert orphan in output
    for related in (video_file, thumb, captions_key):
        assert related not in output


def test_video_metadata_protected_when_video_row_has_no_file(mock_s3):
    """A YouTube video resource usually has file=None. Its caption/thumbnail
    paths in video_files must still be protected -- the related-set scan no
    longer filters on file__isnull, so the file-less row is still inspected.
    """
    website = WebsiteFactory.create(name="yt-site", short_id="yt-site")
    thumb = f"{website.s3_path}/thumb.jpg"
    captions = f"{website.s3_path}/captions.vtt"
    orphan = f"{website.s3_path}/orphan.bin"
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=None,
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_thumbnail_file": thumb,
                "video_captions_file": captions,
                "video_transcript_file": None,
            },
        },
    )
    mock_s3.put({thumb, captions, orphan})

    _run(filter="yt-site", delete=True)

    remaining = mock_s3.current()
    assert thumb in remaining  # protected despite the video row having no file
    assert captions in remaining
    assert orphan not in remaining  # genuine orphan still cleaned


def test_list_all_s3_keys_paginates(mock_s3):
    """list_all_s3_keys collects keys across pages (moto paginates at 1000)."""
    website = WebsiteFactory.create(name="page-site", short_id="page-site")
    keys = {f"{website.s3_path}/obj_{i}.bin" for i in range(1001)}
    mock_s3.put(keys)

    client = get_boto3_resource("s3").meta.client
    found = list_all_s3_keys(client, MOCK_BUCKET_NAME, website.s3_path)

    assert found == keys  # all 1001 returned, i.e. the continuation loop ran


def test_delete_handles_more_than_1000_keys(mock_s3):
    """Deletion handles >1000 keys, chunked under the delete_objects limit."""
    website = WebsiteFactory.create(name="chunk-site", short_id="chunk-site")
    orphans = {f"{website.s3_path}/orphan_{i}.bin" for i in range(1001)}
    mock_s3.put(orphans)

    output = _run(filter="chunk-site", delete=True)

    assert mock_s3.current() == set()  # all 1001 deleted across batches
    assert "Deleted 1001 unrelated files" in output

    tmp = _tempfile_path(output)
    if tmp:
        tmp.unlink(missing_ok=True)


def test_large_result_written_to_tempfile(mock_s3):
    """Result sets over UNRELATED_FILES_THRESHOLD are dumped to a temp file."""
    website = WebsiteFactory.create(name="big-site", short_id="big-site")
    orphans = {f"{website.s3_path}/orphan_{i}.bin" for i in range(101)}
    mock_s3.put(orphans)

    output = _run(filter="big-site")

    tmp = _tempfile_path(output)
    assert tmp is not None, output
    try:
        data = json.loads(tmp.read_text())
        assert set(data["big-site"]) == orphans
    finally:
        tmp.unlink(missing_ok=True)


def test_filter_scopes_processing_to_named_site(mock_s3):
    """--filter restricts which sites are scanned/cleaned."""
    site_a = WebsiteFactory.create(name="alpha", short_id="alpha")
    site_b = WebsiteFactory.create(name="bravo", short_id="bravo")
    a_orphan = f"{site_a.s3_path}/orphan_a.bin"
    b_orphan = f"{site_b.s3_path}/orphan_b.bin"
    mock_s3.put({a_orphan, b_orphan})

    _run(filter="alpha", delete=True)

    remaining = mock_s3.current()
    assert a_orphan not in remaining  # alpha processed and cleaned
    assert b_orphan in remaining  # bravo never touched


# ---------------------------------------------------------------------------
# Regression tests for deletion-safety hardening: each pins a fix that protects
# files which the command would otherwise wrongly flag (and delete).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metadata_key", ["file", "file_location"])
def test_metadata_file_fields_are_treated_as_related(mock_s3, metadata_key):
    """A content's S3 key may live in metadata["file"]/["file_location"], not the
    file column (legacy data). Those files must be protected, not deleted.
    """
    website = WebsiteFactory.create(name="meta-site", short_id="meta-site")
    key = f"{website.s3_path}/legacy_doc.pdf"
    orphan = f"{website.s3_path}/orphan.bin"
    # file column is NULL; the real S3 location is only in metadata.
    WebsiteContentFactory.create(
        website=website, type="resource", file=None, metadata={metadata_key: key}
    )
    mock_s3.put({key, orphan})

    output = _run(filter="meta-site", delete=True)

    remaining = mock_s3.current()
    assert key in remaining  # metadata-referenced file protected
    assert orphan not in remaining  # genuine orphan still cleaned
    assert key not in output


def test_soft_deleted_content_file_is_protected(mock_s3):
    """Files of soft-deleted content must NOT be deleted.

    WebsiteContent.objects (a SafeDeleteManager) hides soft-deleted rows, but the
    command uses all_objects so a soft-deleted resource's file stays in the
    related-set -- soft deletes are reversible, S3 deletes are not.
    """
    website = WebsiteFactory.create(name="softdel-site", short_id="softdel-site")
    key = f"{website.s3_path}/abc_doc.pdf"
    content = WebsiteContentFactory.create(
        website=website, type="resource", file=key, metadata={}
    )
    mock_s3.put({key})

    content.delete()  # soft delete

    output = _run(filter="softdel-site", delete=True)
    assert "No unrelated content found" in output
    assert key in mock_s3.current()  # not deleted


@pytest.mark.parametrize(
    ("scanner", "sibling"),
    [
        # The real prod collision shapes (scripts/find_s3_prefix_collisions.py):
        ("game-theory", "game-theory-and-political-theory"),  # word extension
        ("lie-groups-and-lie-algebras-i", "lie-groups-and-lie-algebras-ii"),  # sequel
        ("japanese-v", "japanese-vi"),  # sequel (letter, no separator)
        ("heavy-metal-101", "heavy-metal-101-2025"),  # term re-run suffix
    ],
)
def test_s3_prefix_does_not_flag_sibling_site_files(mock_s3, scanner, sibling):
    """A site whose s3_path string-prefixes another's must not pull in the
    sibling's keys: the listing prefix is terminated with "/". Covers each real
    prod collision shape (word-extension, sequel i/ii and v/vi, re-run suffix).
    """
    site_a = WebsiteFactory.create(name=scanner)
    site_b = WebsiteFactory.create(name=sibling)
    # Precondition: the scanner's path is a literal string-prefix of the sibling's.
    assert site_b.s3_path.startswith(site_a.s3_path)

    a_key = f"{site_a.s3_path}/a_doc.pdf"
    b_key = f"{site_b.s3_path}/b_doc.pdf"
    WebsiteContentFactory.create(
        website=site_a, type="resource", file=a_key, metadata={}
    )
    WebsiteContentFactory.create(
        website=site_b, type="resource", file=b_key, metadata={}
    )
    mock_s3.put({a_key, b_key})

    # Scan only the scanner site (and delete): the sibling's file must survive.
    output = _run(filter=scanner, delete=True)

    assert b_key not in output
    assert b_key in mock_s3.current()  # sibling's file survives real S3 prefix match
    assert "No unrelated content found" in output


def test_full_run_does_not_delete_sibling_across_prefix_collision(mock_s3):
    """A full (unfiltered) --delete run must not let one course's pass delete a
    colliding sibling's files via the cross-site delete concatenation.
    """
    site_a = WebsiteFactory.create(name="game-theory")
    site_b = WebsiteFactory.create(name="game-theory-and-political-theory")
    a_key = f"{site_a.s3_path}/a_doc.pdf"
    b_key = f"{site_b.s3_path}/b_doc.pdf"
    a_orphan = f"{site_a.s3_path}/orphan.bin"
    WebsiteContentFactory.create(
        website=site_a, type="resource", file=a_key, metadata={}
    )
    WebsiteContentFactory.create(
        website=site_b, type="resource", file=b_key, metadata={}
    )
    mock_s3.put({a_key, b_key, a_orphan})

    _run(delete=True)  # no --filter: every site is processed

    remaining = mock_s3.current()
    assert a_key in remaining  # real files survive
    assert b_key in remaining  # sibling NOT collaterally deleted
    assert a_orphan not in remaining  # genuine orphan still cleaned
