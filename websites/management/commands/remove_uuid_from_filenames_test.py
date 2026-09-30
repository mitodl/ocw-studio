"""Tests for the remove_uuid_from_filenames management command."""  # noqa: INP001

import csv
from io import StringIO

import pytest
from django.core.management import call_command

from gdrive_sync.factories import DriveFileFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands import remove_uuid_from_filenames as command_module
from websites.management.commands.remove_uuid_from_filenames import (
    _collect_renames,
    _execute_renames,
    _with_suffix,
    strip_uuid_prefix,
)
from websites.models import Website, WebsiteContent

pytestmark = pytest.mark.django_db


UUID_PREFIX = "ab3d029952cda060f4afcd811189a591"
UUID_A = "aa3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
UUID_B = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
UUID_C = "cc3d029952cda060f4afcd811189a591"  # pragma: allowlist secret


def _files_in(*websites):
    """Return the queryset handle() builds, limited to *websites*."""
    return (
        WebsiteContent.objects.filter(website__in=websites)
        .filter(file__isnull=False)
        .exclude(file="")
    )


def _contested_trio(website, name="1.jpg", directory=None):
    """Three different files that all strip to *name*, created in pk order."""
    directory = directory or f"sites/{website.name}"
    rows = [
        WebsiteContentFactory.create(
            website=website, file=f"{directory}/{prefix}_{name}"
        )
        for prefix in (UUID_A, UUID_B, UUID_C)
    ]
    return directory, rows


def _fail_copy_for(*source_keys):
    """Build a copy_object side effect that raises only for *source_keys*."""
    blocked = {key.lstrip("/") for key in source_keys}

    def copy_object(**kwargs):
        if kwargs["CopySource"]["Key"] in blocked:
            msg = "copy failed"
            raise RuntimeError(msg)
        return {}

    return copy_object


@pytest.fixture
def mock_s3(mocker):
    """Mock S3 client used by the command."""
    return mocker.patch(
        "websites.management.commands.remove_uuid_from_filenames.get_boto3_client"
    )


# ---------------------------------------------------------------------------
# Unit tests for _collect_renames
# ---------------------------------------------------------------------------


def test_collect_renames_yields_task_for_uuid_prefixed_file():
    """Returns a RenameTask for a file whose basename has a UUID prefix."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    qs = WebsiteContent.objects.filter(pk=content.pk)

    tasks, skipped = _collect_renames(qs)

    assert skipped == 0
    assert len(tasks) == 1
    assert tasks[0].pk == str(content.pk)
    assert tasks[0].old_key == old_key
    assert tasks[0].new_key == f"sites/{website.name}/doc.pdf"
    assert tasks[0].website_id == str(content.website_id)


def test_collect_renames_skips_file_without_uuid_prefix():
    """Files with no UUID prefix are silently skipped and not counted."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/plain.pdf"
    )
    qs = WebsiteContent.objects.filter(pk=content.pk)

    tasks, skipped = _collect_renames(qs)

    assert tasks == []
    assert skipped == 0  # not counted — no UUID prefix at all


def test_collect_renames_skips_and_counts_empty_result_basename():
    """A file whose basename is only <uuid>_ is skipped and counted."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_"
    )
    qs = WebsiteContent.objects.filter(pk=content.pk)

    tasks, skipped = _collect_renames(qs)

    assert tasks == []
    assert skipped == 1


@pytest.mark.parametrize(
    ("filename", "expected_result"),
    [
        # Path with directory prefix
        (
            f"sites/my-course/{UUID_PREFIX}_captions.vtt",
            "sites/my-course/captions.vtt",
        ),
        # Path with no directory
        (f"{UUID_PREFIX}_standalone.pdf", "standalone.pdf"),
        # Path with leading slash
        (
            f"/sites/my-course/{UUID_PREFIX}_captions.vtt",
            "/sites/my-course/captions.vtt",
        ),
        # Path with no UUID prefix should be unchanged
        ("sites/my-course/captions.vtt", "sites/my-course/captions.vtt"),
        # Path where stripping would leave an empty name should be unchanged
        (f"sites/my-course/{UUID_PREFIX}_", f"sites/my-course/{UUID_PREFIX}_"),
    ],
)
def test_strip_uuid_prefix(filename, expected_result):
    assert strip_uuid_prefix(filename) == expected_result


def test_renames_file_with_uuid_prefix(settings, mock_s3):
    """Files whose basename starts with a 32-char hex UUID prefix are renamed in S3 and in the DB."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_document.pdf"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    expected_new_key = f"sites/{website.name}/document.pdf"

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3_client = mock_s3.return_value
    mock_s3_client.copy_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        CopySource={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": old_key},
        Key=expected_new_key,
        ACL="public-read",
    )
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=old_key,
    )
    # copy_object must precede delete_object — data-safe ordering invariant.
    call_names = [c[0] for c in mock_s3_client.mock_calls]
    assert call_names.index("copy_object") < call_names.index("delete_object"), (
        "copy_object must be called before delete_object"
    )
    content.refresh_from_db()
    assert str(content.file) == expected_new_key


def test_also_updates_drive_file(settings, mock_s3):
    """The associated DriveFile.s3_key is updated when it matches the old S3 key."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    drive_file = DriveFileFactory.create(
        resource=content, website=website, s3_key=old_key
    )
    expected_new_key = f"sites/{website.name}/photo.jpg"

    call_command("remove_uuid_from_filenames", filter=website.name)

    drive_file.refresh_from_db()
    assert drive_file.s3_key == expected_new_key


def test_also_updates_drive_file_with_leading_slash_content(settings, mock_s3):
    """DriveFile.s3_key is updated correctly when content.file has a leading slash."""
    website = WebsiteFactory.create()
    old_key_db = f"/courses/{website.name}/{UUID_PREFIX}_photo.jpg"
    content = WebsiteContentFactory.create(website=website, file=old_key_db)
    # DriveFile.s3_key is always stored without a leading slash (backfill normalizes it).
    drive_file = DriveFileFactory.create(
        resource=content,
        website=website,
        s3_key=f"courses/{website.name}/{UUID_PREFIX}_photo.jpg",
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    drive_file.refresh_from_db()
    assert drive_file.s3_key == f"courses/{website.name}/photo.jpg"


def test_skips_file_without_uuid_prefix(mock_s3):
    """Files whose basename does not start with a UUID prefix are left unchanged."""
    website = WebsiteFactory.create()
    plain_key = f"sites/{website.name}/document.pdf"
    content = WebsiteContentFactory.create(website=website, file=plain_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == plain_key


def test_skips_file_with_empty_name_after_uuid_strip(mock_s3):
    """A file whose basename is only the UUID prefix is skipped (stripping would leave an empty name)."""
    website = WebsiteFactory.create()
    # Basename is exactly "<uuid>_" with nothing after the underscore
    empty_result_key = f"sites/{website.name}/{UUID_PREFIX}_"
    content = WebsiteContentFactory.create(website=website, file=empty_result_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == empty_result_key


def test_renames_to_a_suffix_when_the_name_is_held(mock_s3):
    """A held target no longer blocks the rename, the file gets the next free suffix."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_notes.txt"
    source = WebsiteContentFactory.create(website=website, file=old_key)
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/notes.txt"
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    source.refresh_from_db()
    assert str(source.file) == f"sites/{website.name}/notes-2.txt"
    copy = mock_s3.return_value.copy_object
    copy.assert_called_once()
    assert copy.call_args.kwargs["Key"] == f"sites/{website.name}/notes-2.txt"


def test_renames_every_source_that_wants_the_same_name(mock_s3):
    """Two files that strip to one name both rename, the second with a suffix."""
    website = WebsiteFactory.create()
    uuid_b = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    content_a = WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_report.pdf"
    )
    content_b = WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{uuid_b}_report.pdf"
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    content_a.refresh_from_db()
    content_b.refresh_from_db()
    assert str(content_a.file) == f"sites/{website.name}/report.pdf"
    assert str(content_b.file) == f"sites/{website.name}/report-2.pdf"
    assert mock_s3.return_value.copy_object.call_count == 2


def test_dry_run_makes_no_changes(tmp_path, mock_s3):
    """With --dry-run, no S3 operations are performed and the DB is not modified."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_slides.pptx"
    content = WebsiteContentFactory.create(website=website, file=old_key)

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
    )

    mock_s3.return_value.copy_object.assert_not_called()
    mock_s3.return_value.delete_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == old_key


def test_dry_run_reports_metadata_patch_count(tmp_path, mock_s3):
    """Dry-run summary includes the number of video metadata records that would be patched."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    # The file rename will be detected and trigger a metadata patch on the video resource
    WebsiteContentFactory.create(website=website, file=captions_old)
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": None,
            },
        },
    )

    stdout = StringIO()
    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "1 content metadata records would be patched" in output


def test_dry_run_writes_csv_plan(tmp_path, mock_s3):
    """Dry-run exports a CSV with pk, website info, and old/new S3 keys."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    content = WebsiteContentFactory.create(website=website, file=old_key)
    output_file = tmp_path / "plan.csv"

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(output_file),
    )

    assert output_file.exists()
    with output_file.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["pk"] == str(content.pk)
    assert rows[0]["old_key"] == old_key
    assert rows[0]["new_key"] == f"sites/{website.name}/doc.pdf"
    assert rows[0]["website_id"] == str(website.uuid)
    assert rows[0]["website_name"] == website.name


def test_dry_run_requires_output(mock_s3):
    """--dry-run without --output raises CommandError instead of writing to stdout."""
    from django.core.management.base import CommandError  # noqa: PLC0415

    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    )
    with pytest.raises(CommandError, match="--output is required"):
        call_command("remove_uuid_from_filenames", filter=website.name, dry_run=True)


def test_filter_limits_to_specified_website(mock_s3):
    """The --filter argument restricts processing to the named website only."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    key_a = f"sites/{website_a.name}/{UUID_PREFIX}_file.pdf"
    key_b = f"sites/{website_b.name}/{UUID_PREFIX}_file.pdf"
    content_a = WebsiteContentFactory.create(website=website_a, file=key_a)
    content_b = WebsiteContentFactory.create(website=website_b, file=key_b)

    call_command("remove_uuid_from_filenames", filter=website_a.name)

    assert mock_s3.return_value.copy_object.call_count == 1
    content_a.refresh_from_db()
    assert str(content_a.file) == f"sites/{website_a.name}/file.pdf"
    content_b.refresh_from_db()
    assert str(content_b.file) == key_b


def test_s3_error_is_reported_and_does_not_abort(mock_s3):
    """An S3 error on one file is reported and processing continues for other files."""
    website = WebsiteFactory.create()
    failing_key = f"sites/{website.name}/{UUID_PREFIX}_bad.pdf"
    good_uuid = "cc4d029952cda060f4afcd811189a591"
    succeeding_key = f"sites/{website.name}/{good_uuid}_good.pdf"
    failing_content = WebsiteContentFactory.create(website=website, file=failing_key)
    succeeding_content = WebsiteContentFactory.create(
        website=website, file=succeeding_key
    )

    mock_s3.return_value.copy_object.side_effect = [
        Exception("S3 unavailable"),
        None,
    ]

    call_command("remove_uuid_from_filenames", filter=website.name)

    assert mock_s3.return_value.copy_object.call_count == 2
    failing_content.refresh_from_db()
    assert str(failing_content.file) == failing_key
    succeeding_content.refresh_from_db()
    assert str(succeeding_content.file) == f"sites/{website.name}/good.pdf"


def test_s3_error_does_not_dirty_website_or_patch_metadata(mock_s3):
    """A failed rename must not mark the website dirty or patch video metadata."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    captions_content = WebsiteContentFactory.create(website=website, file=captions_old)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": None,
            },
        },
    )
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )
    mock_s3.return_value.copy_object.side_effect = Exception("S3 unavailable")

    call_command("remove_uuid_from_filenames", filter=website.name)

    # Rename failed: file unchanged in DB
    captions_content.refresh_from_db()
    assert str(captions_content.file) == captions_old
    # Website must NOT be marked dirty — no rename committed to DB
    website.refresh_from_db()
    assert website.has_unpublished_live is False
    assert website.has_unpublished_draft is False
    # Video metadata must NOT be patched — the underlying file was not renamed
    video_resource.refresh_from_db()
    assert video_resource.metadata["video_files"]["video_captions_file"] == captions_old


def test_metadata_not_patched_for_a_failed_captions_rename(mock_s3):
    """A rename whose copy fails leaves the metadata pointing at the old file."""
    website = WebsiteFactory.create()
    other_uuid = "cc4d029952cda060f4afcd811189a591"
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{other_uuid}_main.mp4"
    )
    captions_old = f"sites/{website.name}/{UUID_A}_captions.vtt"
    WebsiteContentFactory.create(website=website, file=captions_old)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": None,
            },
        },
    )
    mock_s3.return_value.copy_object.side_effect = _fail_copy_for(captions_old)

    call_command("remove_uuid_from_filenames", filter=website.name)

    video_resource.refresh_from_db()
    assert video_resource.metadata["video_files"]["video_captions_file"] == captions_old


def test_delete_object_failure_still_records_rename(mock_s3):
    """A delete_object failure after a committed copy+DB rename still marks dirty and patches metadata."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    captions_content = WebsiteContentFactory.create(website=website, file=captions_old)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": None,
            },
        },
    )
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )
    mock_s3.return_value.delete_object.side_effect = Exception("Delete failed")

    call_command("remove_uuid_from_filenames", filter=website.name)

    # copy + DB updates committed before delete — rename should be counted
    captions_content.refresh_from_db()
    assert str(captions_content.file) == f"sites/{website.name}/captions.vtt"
    # Website must be marked dirty despite delete failure
    website.refresh_from_db()
    assert website.has_unpublished_live is True
    assert website.has_unpublished_draft is True
    # Metadata must be patched
    video_resource.refresh_from_db()
    assert (
        video_resource.metadata["video_files"]["video_captions_file"]
        == f"sites/{website.name}/captions.vtt"
    )


def test_conflict_detection_normalizes_leading_slash(mock_s3):
    """A held target is detected even when it differs only by a leading slash."""
    website = WebsiteFactory.create()
    # Existing record holds the target path WITHOUT a leading slash.
    existing_key = f"courses/{website.name}/doc.pdf"
    WebsiteContentFactory.create(website=website, file=existing_key)
    # Source has a leading slash and UUID prefix — would rename to /courses/.../doc.pdf.
    # After lstrip normalization, this is the same S3 key as existing_key.
    source_key = f"/courses/{website.name}/{UUID_PREFIX}_doc.pdf"
    WebsiteContentFactory.create(website=website, file=source_key)
    source = WebsiteContent.objects.get(file=source_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    source.refresh_from_db()
    assert str(source.file) == f"/courses/{website.name}/doc-2.pdf"
    copy = mock_s3.return_value.copy_object
    assert copy.call_args.kwargs["Key"] == f"courses/{website.name}/doc-2.pdf"


def test_marks_website_dirty_after_rename(mock_s3):
    """Websites with renamed files are marked as having unpublished changes."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_report.pdf"
    WebsiteContentFactory.create(website=website, file=old_key)
    # Reset flags after content creation (signals set them on save)
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    website.refresh_from_db()
    assert website.has_unpublished_live is True
    assert website.has_unpublished_draft is True


def test_dry_run_does_not_mark_website_dirty(tmp_path, mock_s3):
    """With --dry-run, website dirty flags are not set."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_report.pdf"
    WebsiteContentFactory.create(website=website, file=old_key)
    # Reset flags after content creation (signals set them on save)
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
    )

    website.refresh_from_db()
    assert website.has_unpublished_live is False
    assert website.has_unpublished_draft is False


def test_patches_video_metadata_captions_and_transcript(mock_s3):
    """After renaming captions/transcript files, the parent video resource metadata is updated."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    transcript_old = f"sites/{website.name}/{UUID_PREFIX}_transcript.pdf"
    captions_new = f"sites/{website.name}/captions.vtt"
    transcript_new = f"sites/{website.name}/transcript.pdf"

    WebsiteContentFactory.create(website=website, file=captions_old)
    WebsiteContentFactory.create(website=website, file=transcript_old)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": transcript_old,
            },
        },
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    video_resource.refresh_from_db()
    assert video_resource.metadata["video_files"]["video_captions_file"] == captions_new
    assert (
        video_resource.metadata["video_files"]["video_transcript_file"]
        == transcript_new
    )


def test_renames_file_with_leading_slash_normalizes_s3_key(settings, mock_s3):
    """content.file paths with a leading slash are stripped before S3 operations."""
    website = WebsiteFactory.create()
    # Legacy courses/ content stores file paths with a leading slash in the DB.
    old_key_db = f"/courses/{website.name}/{UUID_PREFIX}_ch8.pdf"
    content = WebsiteContentFactory.create(website=website, file=old_key_db)
    expected_s3_old = f"courses/{website.name}/{UUID_PREFIX}_ch8.pdf"
    expected_s3_new = f"courses/{website.name}/ch8.pdf"

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3_client = mock_s3.return_value
    mock_s3_client.copy_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        CopySource={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": expected_s3_old},
        Key=expected_s3_new,
        ACL="public-read",
    )
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=expected_s3_old,
    )
    content.refresh_from_db()
    # DB value preserves the original leading-slash format; only UUID prefix stripped.
    assert str(content.file) == f"/courses/{website.name}/ch8.pdf"


def test_patches_video_metadata_when_file_has_leading_slash(mock_s3):
    """Metadata is patched correctly when content.file and metadata both use leading-slash paths."""
    website = WebsiteFactory.create()
    captions_old_db = f"/courses/{website.name}/{UUID_PREFIX}_captions.vtt"
    WebsiteContentFactory.create(website=website, file=captions_old_db)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old_db,
                "video_transcript_file": None,
            },
        },
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    video_resource.refresh_from_db()
    expected = f"/courses/{website.name}/captions.vtt"
    assert video_resource.metadata["video_files"]["video_captions_file"] == expected


def test_patches_video_metadata_with_leading_slash(mock_s3):
    """Metadata paths stored with a leading slash are also patched correctly."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"/{captions_old}",
                "video_transcript_file": None,
            },
        },
    )
    WebsiteContentFactory.create(website=website, file=captions_old)

    call_command("remove_uuid_from_filenames", filter=website.name)

    video_resource.refresh_from_db()
    expected = f"/sites/{website.name}/captions.vtt"
    assert video_resource.metadata["video_files"]["video_captions_file"] == expected


def test_patches_file_references_in_any_resource_metadata(mock_s3):
    """Not only video resources: any metadata value naming a renamed file."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    doc = WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=old_key,
        metadata={"resourcetype": "Document", "file": f"/{old_key}"},
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    doc.refresh_from_db()
    assert doc.metadata == {
        "resourcetype": "Document",
        "file": f"/sites/{website.name}/doc.pdf",
    }


def test_leaves_metadata_without_references_alone(mock_s3):
    """Metadata that names no renamed file is not touched."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    )
    other = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={"resourcetype": "Document", "video_files": None},
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    other.refresh_from_db()
    assert other.metadata == {"resourcetype": "Document", "video_files": None}


def test_dry_run_does_not_patch_video_metadata(tmp_path, mock_s3):
    """With --dry-run, video metadata is not modified."""
    website = WebsiteFactory.create()
    captions_old = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    WebsiteContentFactory.create(website=website, file=captions_old)
    video_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": captions_old,
                "video_transcript_file": None,
            },
        },
    )

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
    )

    video_resource.refresh_from_db()
    assert video_resource.metadata["video_files"]["video_captions_file"] == captions_old


def test_patches_gallery_markdown_href(mock_s3):
    """Renaming a file also rewrites any image-gallery-item href that referenced it."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    WebsiteContentFactory.create(website=website, file=old_key)
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}',
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert (
        gallery.markdown
        == '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    )


def test_does_not_patch_gallery_for_a_failed_rename(mock_s3):
    """A rename whose copy fails must not rewrite the gallery href either."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    WebsiteContentFactory.create(website=website, file=old_key)
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)
    mock_s3.return_value.copy_object.side_effect = _fail_copy_for(old_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == original_markdown


def test_dry_run_reports_gallery_patch_count(tmp_path, mock_s3):
    """Dry-run summary includes the number of gallery pages that would be patched."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    WebsiteContentFactory.create(website=website, file=old_key)
    WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}',
    )

    stdout = StringIO()
    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "1 gallery pages would be patched" in output


def test_dry_run_does_not_patch_gallery_markdown(tmp_path, mock_s3):
    """With --dry-run, gallery markdown is not modified."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    WebsiteContentFactory.create(website=website, file=old_key)
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
    )

    gallery.refresh_from_db()
    assert gallery.markdown == original_markdown


def test_gallery_patch_isolated_by_website_via_command(mock_s3):
    """A rename in one website must not touch a byte-identical href in another website.

    Regression test for the command-integrated _PlannedGalleryHrefRule path,
    not just the standalone GalleryImageRenameRule (which already has
    equivalent coverage).
    """
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website_a, file=f"sites/{website_a.name}/{UUID_PREFIX}_photo.jpg"
    )
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery_a = WebsiteContentFactory.create(
        website=website_a, markdown=original_markdown
    )
    gallery_b = WebsiteContentFactory.create(
        website=website_b, markdown=original_markdown
    )

    call_command("remove_uuid_from_filenames")

    gallery_a.refresh_from_db()
    gallery_b.refresh_from_db()
    assert (
        gallery_a.markdown
        == '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    )
    assert gallery_b.markdown == original_markdown


def test_patches_multiple_gallery_items_in_one_body(mock_s3):
    """A single markdown body referencing two different renamed files gets both hrefs updated."""
    website = WebsiteFactory.create()
    uuid_b = "cb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_a.jpg"
    )
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{uuid_b}_b.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="{UUID_PREFIX}_a.jpg" text="first" >}}}}\n'
            f'{{{{< image-gallery-item href="{uuid_b}_b.jpg" text="second" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == (
        '{{< image-gallery-item href="a.jpg" text="first" >}}\n'
        '{{< image-gallery-item href="b.jpg" text="second" >}}'
    )


def test_gallery_scan_survives_malformed_shortcode_elsewhere(mock_s3):
    """A malformed shortcode on one page must not prevent gallery patching on other pages."""
    website = WebsiteFactory.create()
    uuid_b = "db3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_good.jpg"
    )
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{uuid_b}_bad.jpg"
    )
    good_markdown = (
        f'{{{{< image-gallery-item href="{UUID_PREFIX}_good.jpg" text="fine" >}}}}'
    )
    good_gallery = WebsiteContentFactory.create(website=website, markdown=good_markdown)
    # Unquoted nested shortcode -- raises ValueError("... nesting ...") during parsing.
    malformed_markdown = (
        f'{{{{< image-gallery-item href="{uuid_b}_bad.jpg" '
        '{{< sup 4 >}} text="broken" >}}'
    )
    bad_gallery = WebsiteContentFactory.create(
        website=website, markdown=malformed_markdown
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    good_gallery.refresh_from_db()
    bad_gallery.refresh_from_db()
    assert (
        good_gallery.markdown
        == '{{< image-gallery-item href="good.jpg" text="fine" >}}'
    )
    assert bad_gallery.markdown == malformed_markdown


def test_dry_run_writes_csv_even_if_gallery_scan_fails(tmp_path, mock_s3):
    """A malformed shortcode must not prevent the dry-run CSV rename plan from being written."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    WebsiteContentFactory.create(website=website, file=old_key)
    malformed_markdown = (
        f'{{{{< image-gallery-item href="{UUID_PREFIX}_doc.pdf" '
        '{{< sup 4 >}} text="broken" >}}'
    )
    WebsiteContentFactory.create(website=website, markdown=malformed_markdown)
    output_file = tmp_path / "plan.csv"

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(output_file),
    )

    assert output_file.exists()
    with output_file.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["old_key"] == old_key


def test_gallery_uuid_param_resolves_href_that_basename_matching_would_miss(mock_s3):
    """The uuid param names the renamed resource, so a stale href is still corrected."""
    website = WebsiteFactory.create()
    image_uuid = "ab3d0299-52cd-a060-f4af-cd811189a591"  # pragma: allowlist secret
    WebsiteContentFactory.create(
        website=website,
        text_id=image_uuid,
        file=f"sites/{website.name}/{UUID_PREFIX}_actual.jpg",
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item uuid="{image_uuid}" '
            f'href="{UUID_PREFIX}_stale.jpg" text="a caption" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == (
        f'{{{{< image-gallery-item uuid="{image_uuid}" '
        'href="actual.jpg" text="a caption" >}}'
    )


def test_gallery_uuid_param_is_preserved_alongside_rewritten_href(mock_s3):
    """The uuid image_gallery_item_uuid added survives the href rewrite."""
    website = WebsiteFactory.create()
    image_uuid = "ab3d0299-52cd-a060-f4af-cd811189a591"  # pragma: allowlist secret
    WebsiteContentFactory.create(
        website=website,
        text_id=image_uuid,
        file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg",
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item uuid="{image_uuid}" '
            f'href="{UUID_PREFIX}_photo.jpg" data-ngdesc="A rock" text="cap" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == (
        f'{{{{< image-gallery-item uuid="{image_uuid}" '
        'href="photo.jpg" data-ngdesc="A rock" text="cap" >}}'
    )


def test_gallery_path_valued_href_keeps_its_path(mock_s3):
    """A path-valued gallery href is repaired without losing its directory."""
    website = WebsiteFactory.create()
    image_uuid = "ab3d0299-52cd-a060-f4af-cd811189a591"  # pragma: allowlist secret
    WebsiteContentFactory.create(
        website=website,
        text_id=image_uuid,
        file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg",
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item uuid="{image_uuid}" '
            f'href="/courses/{website.name}/{UUID_PREFIX}_photo.jpg" text="cap" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == (
        f'{{{{< image-gallery-item uuid="{image_uuid}" '
        f'href="/courses/{website.name}/photo.jpg" text="cap" >}}}}'
    )


def test_gallery_scan_clears_bookkeeping_for_malformed_pages(mocker, mock_s3):
    """A page that fails to parse must not leave match bookkeeping behind."""
    from websites.management.commands import (  # noqa: PLC0415
        remove_uuid_from_filenames as command_module,
    )
    from websites.management.commands.remove_uuid_from_filenames import (  # noqa: PLC0415
        _collect_markdown_patches,
        _collect_renames,
    )

    cleaners = []
    real_cleaner = command_module.WebsiteContentMarkdownCleaner

    def capture(rule):
        instance = real_cleaner(rule)
        cleaners.append(instance)
        return instance

    mocker.patch.object(
        command_module, "WebsiteContentMarkdownCleaner", side_effect=capture
    )

    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_good.jpg"
    )
    # A valid item followed by an unquoted nested shortcode on the same page.
    WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="{UUID_PREFIX}_good.jpg" text="ok" >}}}}\n'
            '{{< image-gallery-item {{< sup 4 >}} text="broken" >}}'
        ),
    )

    renames, _ = _collect_renames(
        WebsiteContent.objects.filter(website=website)
        .filter(file__isnull=False)
        .exclude(file="")
    )
    # Must not raise, and must not leave the failed page's matches behind.
    _collect_markdown_patches(renames, {})

    assert cleaners, "expected the scan to build a cleaner"
    assert cleaners[0].replacement_matches == []


def test_gallery_patch_refreshes_content_sync_state(mock_s3):
    """bulk_update skips post_save, so the sync state must be refreshed explicitly.

    Without this the row keeps current_checksum == synced_checksum, which
    upsert_content_files_for_user treats as already synced and excludes, so the
    markdown fix never reaches git.
    """
    from content_sync.models import ContentSyncState  # noqa: PLC0415

    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="cap" >}}}}',
    )
    # Put the row in the "already synced" state the exclusion filter looks for.
    state = ContentSyncState.objects.get(content=gallery)
    state.synced_checksum = state.current_checksum
    state.save()

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    state.refresh_from_db()
    assert 'href="photo.jpg"' in gallery.markdown
    assert state.current_checksum == gallery.calculate_checksum()
    assert state.current_checksum != state.synced_checksum


@pytest.fixture
def mock_sync(mocker):
    """Mock the backend sync task the command kicks off after a live run."""
    return mocker.patch(
        "websites.management.commands.remove_uuid_from_filenames.sync_website_content"
    )


def _website_with_rename():
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    )
    return website


def test_triggers_sync_after_a_live_run(settings, mock_s3, mock_sync):
    """A live run that changed something pushes it to the configured backend."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = _website_with_rename()

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_sync.delay.assert_called_once_with(website.name)


def test_sync_is_scoped_to_the_websites_that_changed(settings, mock_s3, mock_sync):
    """An untouched website must not be dragged into the push."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    renamed = _website_with_rename()
    untouched = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=untouched, file=f"sites/{untouched.name}/plain.pdf"
    )

    call_command("remove_uuid_from_filenames")

    synced = {call.args[0] for call in mock_sync.delay.call_args_list}
    assert synced == {renamed.name}


def test_skip_sync_suppresses_the_sync_task(settings, mock_s3, mock_sync):
    """--skip-sync leaves the push to the operator."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = _website_with_rename()

    call_command("remove_uuid_from_filenames", filter=website.name, skip_sync=True)

    mock_sync.delay.assert_not_called()


def test_dry_run_never_triggers_sync(settings, tmp_path, mock_s3, mock_sync):
    """A dry run changes nothing, so there is nothing to push."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = _website_with_rename()

    call_command(
        "remove_uuid_from_filenames",
        filter=website.name,
        dry_run=True,
        output=str(tmp_path / "plan.csv"),
    )

    mock_sync.delay.assert_not_called()


def test_no_sync_without_a_content_sync_backend(settings, mock_s3, mock_sync):
    """With no backend configured there is nowhere to sync to."""
    settings.CONTENT_SYNC_BACKEND = None
    website = _website_with_rename()

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_sync.delay.assert_not_called()


def test_no_sync_when_the_run_changed_nothing(settings, mock_s3, mock_sync):
    """A run with no renames must not kick off a global sync of unrelated sites."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/plain.pdf"
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_sync.delay.assert_not_called()


def test_sync_failure_is_reported_without_aborting(settings, mock_s3, mock_sync):
    """A site that fails to sync must not abort a run whose renames already committed."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = _website_with_rename()
    content = WebsiteContent.objects.get(website=website, file__contains=UUID_PREFIX)
    mock_sync.delay.return_value.get.side_effect = OSError("github is unhappy")

    stderr = StringIO()
    call_command("remove_uuid_from_filenames", filter=website.name, stderr=stderr)

    # The rename still stands, and the operator is told what still needs publishing.
    content.refresh_from_db()
    assert str(content.file) == f"sites/{website.name}/doc.pdf"
    assert "did not sync" in stderr.getvalue()


def test_sync_waits_with_a_timeout(settings, mock_s3, mock_sync):
    """Blocking on a worker that never answers would hang the command forever."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = _website_with_rename()

    call_command("remove_uuid_from_filenames", filter=website.name)

    _, kwargs = mock_sync.delay.return_value.get.call_args
    assert kwargs.get("timeout")


def test_rename_refreshes_sync_state_before_the_run_ends(settings, mock_s3, mock_sync):
    """Each rename's sync state is committed with it, not deferred to the end."""
    from content_sync.models import ContentSyncState  # noqa: PLC0415

    settings.CONTENT_SYNC_BACKEND = None
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    )
    state = ContentSyncState.objects.get(content=content)
    state.synced_checksum = state.current_checksum
    state.save()

    call_command("remove_uuid_from_filenames", filter=website.name)

    content.refresh_from_db()
    state.refresh_from_db()
    assert state.current_checksum == content.calculate_checksum()


def test_sync_timeout_stops_dispatching_further_sites(settings, mock_s3, mock_sync):
    """get(timeout) does not stop the worker, so dispatching on would overlap syncs."""
    from celery.exceptions import TimeoutError as CeleryTimeoutError  # noqa: PLC0415

    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    first = _website_with_rename()
    second = _website_with_rename()
    mock_sync.delay.return_value.get.side_effect = CeleryTimeoutError("no answer")

    stderr = StringIO()
    call_command("remove_uuid_from_filenames", stderr=stderr)

    # Only the first site is dispatched, and both are reported as unsynced.
    assert mock_sync.delay.call_count == 1
    message = stderr.getvalue()
    assert "Timed out" in message
    assert first.name in message or second.name in message


@pytest.mark.parametrize(
    ("key", "number", "expected"),
    [
        ("sites/site/1.jpg", 2, "sites/site/1-2.jpg"),
        ("sites/site/archive.tar.gz", 2, "sites/site/archive.tar-2.gz"),
        ("sites/site/name", 3, "sites/site/name-3"),
        ("notes.PDF", 21, "notes-21.PDF"),
    ],
)
def test_with_suffix_goes_before_the_last_extension(key, number, expected):
    """The extension stays last, which caption pairing and downloads rely on."""
    assert _with_suffix(key, number) == expected


def test_contested_names_get_suffixes_in_pk_order():
    """The lowest pk keeps the plain name and the rest count up from -2."""
    website = WebsiteFactory.create()
    directory, (first, second, third) = _contested_trio(website)

    tasks, skipped = _collect_renames(_files_in(website))

    assert skipped == 0
    by_pk = {task.pk: task for task in tasks}
    assert by_pk[str(first.pk)].new_key == f"{directory}/1.jpg"
    assert by_pk[str(second.pk)].new_key == f"{directory}/1-2.jpg"
    assert by_pk[str(third.pk)].new_key == f"{directory}/1-3.jpg"
    assert [by_pk[str(row.pk)].suffixed for row in (first, second, third)] == [
        False,
        True,
        True,
    ]
    assert {task.reason for task in tasks} == {"contested"}


def test_name_held_by_an_existing_file_suffixes_every_candidate():
    """A file that is not being renamed keeps its name."""
    website = WebsiteFactory.create()
    directory = f"sites/{website.name}"
    WebsiteContentFactory.create(website=website, file=f"{directory}/notes.txt")
    source = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_A}_notes.txt"
    )

    tasks, skipped = _collect_renames(_files_in(website).filter(pk=source.pk))

    assert skipped == 0
    assert [(task.new_key, task.suffixed, task.reason) for task in tasks] == [
        (f"{directory}/notes-2.txt", True, "name held by existing file")
    ]


def test_a_taken_suffix_is_skipped():
    """If -2 is already a real file, the next file gets -3."""
    website = WebsiteFactory.create()
    directory = f"sites/{website.name}"
    WebsiteContentFactory.create(website=website, file=f"{directory}/1-2.jpg")
    first = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_A}_1.jpg"
    )
    second = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_B}_1.jpg"
    )

    tasks, _ = _collect_renames(_files_in(website))

    assert {task.pk: task.new_key for task in tasks} == {
        str(first.pk): f"{directory}/1.jpg",
        str(second.pk): f"{directory}/1-3.jpg",
    }


def test_a_soft_deleted_file_still_blocks_its_name():
    """Its S3 object may still exist, so the name is never reused."""
    website = WebsiteFactory.create()
    directory = f"sites/{website.name}"
    WebsiteContentFactory.create(website=website, file=f"{directory}/1-2.jpg").delete()
    WebsiteContentFactory.create(website=website, file=f"{directory}/{UUID_A}_1.jpg")
    second = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_B}_1.jpg"
    )

    tasks, _ = _collect_renames(_files_in(website))

    assert {task.pk: task.new_key for task in tasks}[str(second.pk)] == (
        f"{directory}/1-3.jpg"
    )


def test_plain_names_are_claimed_before_any_suffix():
    """A file originally named 1-2.jpg keeps it although a 1.jpg group needs suffixes."""
    website = WebsiteFactory.create()
    directory = f"sites/{website.name}"
    first = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_A}_1.jpg"
    )
    second = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_B}_1.jpg"
    )
    own = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_C}_1-2.jpg"
    )

    tasks, _ = _collect_renames(_files_in(website))

    assert {task.pk: task.new_key for task in tasks} == {
        str(first.pk): f"{directory}/1.jpg",
        str(second.pk): f"{directory}/1-3.jpg",
        str(own.pk): f"{directory}/1-2.jpg",
    }


def test_numeric_names_never_run_together():
    """Suffixes use a separator, so a 1.jpg group cannot produce 12.jpg."""
    website = WebsiteFactory.create()
    directory = f"sites/{website.name}"
    first = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_A}_1.jpg"
    )
    second = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_B}_1.jpg"
    )
    twelve = WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_C}_12.jpg"
    )

    tasks, _ = _collect_renames(_files_in(website))

    assert {task.pk: task.new_key for task in tasks} == {
        str(first.pk): f"{directory}/1.jpg",
        str(second.pk): f"{directory}/1-2.jpg",
        str(twelve.pk): f"{directory}/12.jpg",
    }


def test_rows_sharing_one_object_rename_together():
    """One S3 object used by two rows is one rename, each row keeps its slash form."""
    first_site = WebsiteFactory.create()
    second_site = WebsiteFactory.create()
    key = f"courses/{first_site.name}/{UUID_A}_doc.pdf"
    first = WebsiteContentFactory.create(website=first_site, file=key)
    second = WebsiteContentFactory.create(website=second_site, file=f"/{key}")

    tasks, skipped = _collect_renames(_files_in(first_site, second_site))

    assert skipped == 0
    by_pk = {task.pk: task for task in tasks}
    assert by_pk[str(first.pk)].new_key == f"courses/{first_site.name}/doc.pdf"
    assert by_pk[str(second.pk)].new_key == f"/courses/{first_site.name}/doc.pdf"
    assert {task.reason for task in tasks} == {"shared object"}
    assert not any(task.suffixed for task in tasks)


def test_an_object_shared_with_an_unselected_website_is_skipped(capsys):
    """Renaming it for one row would delete the object the other row still uses."""
    first_site = WebsiteFactory.create()
    second_site = WebsiteFactory.create()
    key = f"courses/{first_site.name}/{UUID_A}_doc.pdf"
    WebsiteContentFactory.create(website=first_site, file=key)
    WebsiteContentFactory.create(website=second_site, file=key)

    tasks, skipped = _collect_renames(_files_in(first_site))

    assert tasks == []
    assert skipped == 1
    assert second_site.name in capsys.readouterr().err


def test_a_filtered_run_respects_names_held_elsewhere():
    """A name held by an unselected website's row is still taken."""
    first_site = WebsiteFactory.create()
    second_site = WebsiteFactory.create()
    directory = f"sites/{first_site.name}"
    WebsiteContentFactory.create(website=second_site, file=f"{directory}/doc.pdf")
    WebsiteContentFactory.create(
        website=first_site, file=f"{directory}/{UUID_A}_doc.pdf"
    )

    tasks, _ = _collect_renames(_files_in(first_site))

    assert [task.new_key for task in tasks] == [f"{directory}/doc-2.pdf"]


def test_replanning_after_a_partial_run_keeps_the_same_names():
    """Files that committed hold their keys, so pending files get the same names."""
    website = WebsiteFactory.create()
    _, rows = _contested_trio(website)
    tasks, _ = _collect_renames(_files_in(website))
    first_plan = {task.pk: task.new_key for task in tasks}
    middle = rows[1]
    WebsiteContent.objects.filter(pk=middle.pk).update(file=first_plan[str(middle.pk)])

    tasks, _ = _collect_renames(_files_in(website))

    assert {task.pk: task.new_key for task in tasks} == {
        pk: key for pk, key in first_plan.items() if pk != str(middle.pk)
    }


def test_contested_files_are_each_copied_to_their_own_name(mock_s3):
    """Every source object is copied to the key the plan gave it."""
    website = WebsiteFactory.create()
    directory, rows = _contested_trio(website)
    drive_file = DriveFileFactory.create(
        resource=rows[2], website=website, s3_key=f"{directory}/{UUID_C}_1.jpg"
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    drive_file.refresh_from_db()
    assert drive_file.s3_key == f"{directory}/1-3.jpg"
    copies = {
        call.kwargs["CopySource"]["Key"]: call.kwargs["Key"]
        for call in mock_s3.return_value.copy_object.call_args_list
    }
    assert copies == {
        f"{directory}/{UUID_A}_1.jpg": f"{directory}/1.jpg",
        f"{directory}/{UUID_B}_1.jpg": f"{directory}/1-2.jpg",
        f"{directory}/{UUID_C}_1.jpg": f"{directory}/1-3.jpg",
    }


def test_a_shared_object_is_copied_and_deleted_once(mock_s3):
    """Both rows move to the new key, each in its own slash form."""
    first_site = WebsiteFactory.create()
    second_site = WebsiteFactory.create()
    key = f"courses/{first_site.name}/{UUID_A}_doc.pdf"
    first = WebsiteContentFactory.create(website=first_site, file=key)
    second = WebsiteContentFactory.create(website=second_site, file=f"/{key}")

    call_command(
        "remove_uuid_from_filenames", filter=f"{first_site.name},{second_site.name}"
    )

    assert mock_s3.return_value.copy_object.call_count == 1
    assert mock_s3.return_value.delete_object.call_count == 1
    first.refresh_from_db()
    second.refresh_from_db()
    assert str(first.file) == f"courses/{first_site.name}/doc.pdf"
    assert str(second.file) == f"/courses/{first_site.name}/doc.pdf"


def test_a_shared_object_is_kept_while_any_row_still_points_at_it(mocker, mock_s3):
    """If one row fails to commit, the old object must survive for it."""
    first_site = WebsiteFactory.create()
    second_site = WebsiteFactory.create()
    key = f"courses/{first_site.name}/{UUID_A}_doc.pdf"
    first = WebsiteContentFactory.create(website=first_site, file=key)
    second = WebsiteContentFactory.create(website=second_site, file=key)
    real_refresh = command_module._refresh_sync_states  # noqa: SLF001

    def refresh(pks):
        if str(second.pk) in {str(pk) for pk in pks}:
            msg = "boom"
            raise RuntimeError(msg)
        return real_refresh(pks)

    mocker.patch.object(command_module, "_refresh_sync_states", side_effect=refresh)

    call_command(
        "remove_uuid_from_filenames", filter=f"{first_site.name},{second_site.name}"
    )

    mock_s3.return_value.delete_object.assert_not_called()
    first.refresh_from_db()
    second.refresh_from_db()
    assert str(first.file) == f"courses/{first_site.name}/doc.pdf"
    assert str(second.file) == key


def test_a_target_taken_after_planning_skips_its_group(mock_s3):
    """A Drive sync can create the target name while a long run is going."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_A}_doc.pdf"
    )
    renames, _ = _collect_renames(_files_in(website))
    WebsiteContentFactory.create(website=website, file=f"sites/{website.name}/doc.pdf")
    stderr = StringIO()

    result = _execute_renames(renames, mock_s3.return_value, StringIO(), stderr)

    mock_s3.return_value.copy_object.assert_not_called()
    assert result.committed == []
    assert result.error_count == 1
    assert "taken after planning" in stderr.getvalue()


def test_metadata_file_follows_its_own_source(mock_s3):
    """Each row's metadata file follows its own file, not the plain-named sibling."""
    website = WebsiteFactory.create()
    directory, rows = _contested_trio(website)
    third = rows[2]
    WebsiteContent.objects.filter(pk=third.pk).update(
        metadata={"file": f"/{directory}/{UUID_C}_1.jpg"}
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    third.refresh_from_db()
    assert third.metadata["file"] == f"/{directory}/1-3.jpg"


def test_video_metadata_follows_its_own_source(mock_s3):
    """A captions path follows its own file through a suffix."""
    website = WebsiteFactory.create()
    directory, _ = _contested_trio(website, name="captions.vtt")
    video = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"{directory}/{UUID_C}_captions.vtt",
                "video_transcript_file": None,
            },
        },
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    video.refresh_from_db()
    assert video.metadata["video_files"]["video_captions_file"] == (
        f"{directory}/captions-3.vtt"
    )


def test_a_row_stored_under_another_sites_directory_gets_its_metadata_patched(mock_s3):
    """Some duplicate site records keep their files under another site's directory."""
    home_site = WebsiteFactory.create()
    duplicate_site = WebsiteFactory.create()
    key = f"courses/{home_site.name}/{UUID_A}_doc.pdf"
    row = WebsiteContentFactory.create(
        website=duplicate_site, file=key, metadata={"file": f"/{key}"}
    )

    call_command("remove_uuid_from_filenames", filter=duplicate_site.name)

    row.refresh_from_db()
    assert row.metadata["file"] == f"/courses/{home_site.name}/doc.pdf"


def test_gallery_hrefs_follow_their_own_source(mock_s3):
    """Both the bare href and the uuid param resolve to the file's own new name."""
    website = WebsiteFactory.create()
    _, rows = _contested_trio(website)
    third = rows[2]
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="{UUID_C}_1.jpg" text="bare" >}}}}\n'
            f'{{{{< image-gallery-item href="stale.jpg" uuid="{third.text_id}" text="by uuid" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    gallery.refresh_from_db()
    assert gallery.markdown == (
        '{{< image-gallery-item href="1-3.jpg" text="bare" >}}\n'
        f'{{{{< image-gallery-item href="1-3.jpg" uuid="{third.text_id}" text="by uuid" >}}}}'
    )


def test_markdown_file_links_follow_their_own_source(mock_s3):
    """Absolute and root-relative links are rewritten, the rest of the page stays."""
    website = WebsiteFactory.create()
    directory, _ = _contested_trio(website)
    page = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f"![a](https://ocw.mit.edu/{directory}/{UUID_C}_1.jpg) "
            f"and [b](/{directory}/{UUID_C}_1.jpg)."
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    page.refresh_from_db()
    assert page.markdown == (
        f"![a](https://ocw.mit.edu/{directory}/1-3.jpg) and [b](/{directory}/1-3.jpg)."
    )


def test_a_page_with_a_gallery_item_and_a_file_link_keeps_both_patches(mock_s3):
    """Both rewrites land in one saved value, neither overwrites the other."""
    website = WebsiteFactory.create()
    directory, _ = _contested_trio(website)
    page = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="{UUID_A}_1.jpg" text="g" >}}}}\n'
            f"[doc](/{directory}/{UUID_C}_1.jpg)"
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    page.refresh_from_db()
    assert page.markdown == (
        '{{< image-gallery-item href="1.jpg" text="g" >}}\n'
        f"[doc](/{directory}/1-3.jpg)"
    )


def test_a_path_valued_gallery_href_is_rewritten_once(mock_s3):
    """The gallery pass rewrites it, so the link pass no longer sees a prefix."""
    website = WebsiteFactory.create()
    directory, _ = _contested_trio(website)
    page = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="/{directory}/{UUID_B}_1.jpg" text="g" >}}}}'
        ),
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    page.refresh_from_db()
    assert page.markdown == (
        f'{{{{< image-gallery-item href="/{directory}/1-2.jpg" text="g" >}}}}'
    )


def test_a_link_from_another_site_is_patched(mock_s3):
    """The markdown scan covers every website, not only the renamed one."""
    home_site = WebsiteFactory.create()
    other_site = WebsiteFactory.create()
    old_key = f"sites/{home_site.name}/{UUID_PREFIX}_doc.pdf"
    WebsiteContentFactory.create(website=home_site, file=old_key)
    page = WebsiteContentFactory.create(
        website=other_site, markdown=f"[doc](/{old_key})"
    )

    call_command("remove_uuid_from_filenames", filter=home_site.name)

    page.refresh_from_db()
    assert page.markdown == f"[doc](/sites/{home_site.name}/doc.pdf)"


def test_a_link_through_the_published_path_is_patched(mock_s3):
    """A site can publish under url_path while storing files under s3_path."""
    website = WebsiteFactory.create()
    assert website.url_path != website.s3_path
    WebsiteContentFactory.create(
        website=website, file=f"{website.s3_path}/{UUID_PREFIX}_doc.pdf"
    )
    page = WebsiteContentFactory.create(
        website=website,
        markdown=f"[doc](/{website.url_path}/{UUID_PREFIX}_doc.pdf)",
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    page.refresh_from_db()
    assert page.markdown == f"[doc](/{website.url_path}/doc.pdf)"


def test_course_image_urls_follow_their_own_source(mock_s3):
    """The legacy course image values follow their own files, other keys stay."""
    website = WebsiteFactory.create()
    directory, _ = _contested_trio(website)
    WebsiteContentFactory.create(
        website=website, file=f"{directory}/{UUID_PREFIX}_th.jpg"
    )
    Website.objects.filter(pk=website.pk).update(
        metadata={
            "course_image_url": f"/{directory}/{UUID_C}_1.jpg",
            "course_thumbnail_image_url": f"/{directory}/{UUID_PREFIX}_th.jpg",
            "course_title": "Kept",
        }
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    website.refresh_from_db()
    assert website.metadata == {
        "course_image_url": f"/{directory}/1-3.jpg",
        "course_thumbnail_image_url": f"/{directory}/th.jpg",
        "course_title": "Kept",
    }
