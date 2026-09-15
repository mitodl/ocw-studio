"""Tests for the remove_uuid_from_filenames management command."""  # noqa: INP001

import csv
from io import StringIO

import pytest
from django.core.management import call_command

from gdrive_sync.factories import DriveFileFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.remove_uuid_from_filenames import (
    _collect_metadata_patches,
    _collect_renames,
    strip_uuid_prefix,
)
from websites.models import Website, WebsiteContent

pytestmark = pytest.mark.django_db


UUID_PREFIX = "ab3d029952cda060f4afcd811189a591"


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


def test_collect_renames_skips_and_counts_conflict():
    """A file is skipped when its target key is already held by another record."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_notes.txt"
    new_key = f"sites/{website.name}/notes.txt"
    source = WebsiteContentFactory.create(website=website, file=old_key)
    WebsiteContentFactory.create(website=website, file=new_key)  # occupies target
    qs = WebsiteContent.objects.filter(pk=source.pk)

    tasks, skipped = _collect_renames(qs)

    assert tasks == []
    assert skipped == 1


def test_collect_renames_skips_intra_conflict():
    """When two UUID-prefixed records want the same target, both are skipped."""
    website = WebsiteFactory.create()
    uuid_b = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    key_a = f"sites/{website.name}/{UUID_PREFIX}_file.pdf"
    key_b = f"sites/{website.name}/{uuid_b}_file.pdf"
    content_a = WebsiteContentFactory.create(website=website, file=key_a)
    content_b = WebsiteContentFactory.create(website=website, file=key_b)
    qs = WebsiteContent.objects.filter(pk__in=[content_a.pk, content_b.pk]).order_by(
        "pk"
    )

    tasks, skipped = _collect_renames(qs)

    # Both sources target the same key — neither should be renamed.
    assert tasks == []
    assert skipped == 2


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


def test_skips_conflicting_target_key(mock_s3):
    """A file is skipped when the target key is already used by another WebsiteContent."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_notes.txt"
    new_key = f"sites/{website.name}/notes.txt"
    WebsiteContentFactory.create(website=website, file=old_key)
    WebsiteContentFactory.create(website=website, file=new_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()


def test_skips_all_when_multiple_sources_target_same_key(mock_s3):
    """When two UUID-prefixed files resolve to the same target, neither is renamed."""
    website = WebsiteFactory.create()
    uuid_b = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    key_a = f"sites/{website.name}/{UUID_PREFIX}_report.pdf"
    key_b = f"sites/{website.name}/{uuid_b}_report.pdf"
    content_a = WebsiteContentFactory.create(website=website, file=key_a)
    content_b = WebsiteContentFactory.create(website=website, file=key_b)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()
    content_a.refresh_from_db()
    content_b.refresh_from_db()
    assert str(content_a.file) == key_a
    assert str(content_b.file) == key_b


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
    assert "1 video metadata records would be patched" in output


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


def test_metadata_not_patched_for_skipped_captions_rename(mock_s3):
    """Video metadata is not patched when the captions file rename was skipped (conflict)."""
    website = WebsiteFactory.create()
    # File A renames successfully — puts website into actually_renamed_website_ids.
    other_uuid = "cc4d029952cda060f4afcd811189a591"
    old_key_a = f"sites/{website.name}/{other_uuid}_main.mp4"
    WebsiteContentFactory.create(website=website, file=old_key_a)
    # Captions file B: rename skipped — target key is already occupied.
    captions_uuid = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    captions_old = f"sites/{website.name}/{captions_uuid}_captions.vtt"
    captions_new = f"sites/{website.name}/captions.vtt"
    WebsiteContentFactory.create(website=website, file=captions_old)
    WebsiteContentFactory.create(website=website, file=captions_new)  # occupies target
    # Video resource references the skipped captions file.
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

    call_command("remove_uuid_from_filenames", filter=website.name)

    # Captions rename was skipped — metadata must NOT be patched to the stripped path.
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
    """A conflict is detected even when the existing target key and the rename target differ only by leading slash."""
    website = WebsiteFactory.create()
    # Existing record holds the target path WITHOUT a leading slash.
    existing_key = f"courses/{website.name}/doc.pdf"
    WebsiteContentFactory.create(website=website, file=existing_key)
    # Source has a leading slash and UUID prefix — would rename to /courses/.../doc.pdf.
    # After lstrip normalization, this is the same S3 key as existing_key.
    source_key = f"/courses/{website.name}/{UUID_PREFIX}_doc.pdf"
    WebsiteContentFactory.create(website=website, file=source_key)

    call_command("remove_uuid_from_filenames", filter=website.name)

    mock_s3.return_value.copy_object.assert_not_called()


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


def test_does_not_patch_non_video_resource_metadata(mock_s3):
    """Metadata patching only touches records with resourcetype=Video."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_doc.pdf"
    doc_resource = WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=old_key,
        metadata={"resourcetype": "Document", "video_files": None},
    )

    call_command("remove_uuid_from_filenames", filter=website.name)

    doc_resource.refresh_from_db()
    assert doc_resource.metadata.get("video_files") is None


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


def test_does_not_patch_gallery_for_skipped_collision(mock_s3):
    """A collision-skipped rename must not rewrite the gallery href either."""
    website = WebsiteFactory.create()
    uuid_b = "bb3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
    # Two sources collide on the same target -- both get skipped.
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    )
    WebsiteContentFactory.create(
        website=website,
        file=f"sites/{website.name}/{uuid_b}_photo.jpg",
    )
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

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


# ---------------------------------------------------------------------------
# Unit tests for _collect_metadata_patches
# ---------------------------------------------------------------------------


def test_collect_metadata_patches_captions():
    """Returns a MetadataPatch when video_captions_file has a UUID prefix."""
    website = WebsiteFactory.create()
    old_captions = f"sites/{website.name}/{UUID_PREFIX}_captions.vtt"
    video = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": old_captions,
                "video_transcript_file": None,
            },
        },
    )

    patches = _collect_metadata_patches({str(website.uuid)})

    assert len(patches) == 1
    assert patches[0].pk == str(video.pk)
    vf = patches[0].updated_metadata["video_files"]
    assert vf["video_captions_file"] == f"sites/{website.name}/captions.vtt"
    assert vf["video_transcript_file"] is None


def test_collect_metadata_patches_transcript():
    """Returns a MetadataPatch when video_transcript_file has a UUID prefix."""
    website = WebsiteFactory.create()
    old_transcript = f"sites/{website.name}/{UUID_PREFIX}_transcript.pdf"
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": None,
                "video_transcript_file": old_transcript,
            },
        },
    )

    patches = _collect_metadata_patches({str(website.uuid)})

    assert len(patches) == 1
    vf = patches[0].updated_metadata["video_files"]
    assert vf["video_transcript_file"] == f"sites/{website.name}/transcript.pdf"


def test_collect_metadata_patches_no_uuid_prefix_returns_empty():
    """Returns nothing when metadata paths have no UUID prefix."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"sites/{website.name}/captions.vtt",
                "video_transcript_file": None,
            },
        },
    )

    patches = _collect_metadata_patches({str(website.uuid)})

    assert patches == []


def test_collect_metadata_patches_ignores_non_video_resource():
    """Records with resourcetype != Video are not patched."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Document",
            "video_files": {
                "video_captions_file": f"sites/{website.name}/{UUID_PREFIX}_cap.vtt",
            },
        },
    )

    patches = _collect_metadata_patches({str(website.uuid)})

    assert patches == []


def test_collect_metadata_patches_handles_null_values():
    """None values in captions/transcript fields do not raise errors."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": None,
                "video_transcript_file": None,
            },
        },
    )

    patches = _collect_metadata_patches({str(website.uuid)})

    assert patches == []


def test_collect_metadata_patches_scoped_to_website_uuids():
    """Only patches records in the supplied website UUID set."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    old_captions = f"sites/{website_b.name}/{UUID_PREFIX}_cap.vtt"
    WebsiteContentFactory.create(
        website=website_b,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": old_captions,
                "video_transcript_file": None,
            },
        },
    )

    # Only pass website_a's UUID — website_b's record must not appear
    patches = _collect_metadata_patches({str(website_a.uuid)})

    assert patches == []


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
        _collect_gallery_patches,
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
    _collect_gallery_patches(renames)

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
