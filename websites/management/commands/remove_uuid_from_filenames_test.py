"""Tests for the remove_uuid_from_filenames management command."""  # noqa: INP001

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
    """When two UUID-prefixed records want the same target, the second is skipped."""
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

    # First record in pk order wins; second is a conflict
    assert len(tasks) + skipped == 2
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


def test_dry_run_makes_no_changes(mock_s3):
    """With --dry-run, no S3 operations are performed and the DB is not modified."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_slides.pptx"
    content = WebsiteContentFactory.create(website=website, file=old_key)

    call_command("remove_uuid_from_filenames", filter=website.name, dry_run=True)

    mock_s3.return_value.copy_object.assert_not_called()
    mock_s3.return_value.delete_object.assert_not_called()
    content.refresh_from_db()
    assert str(content.file) == old_key


def test_dry_run_reports_metadata_patch_count(mock_s3):
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
        stdout=stdout,
    )

    output = stdout.getvalue()
    assert "1 video metadata records would be patched" in output


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


def test_dry_run_does_not_mark_website_dirty(mock_s3):
    """With --dry-run, website dirty flags are not set."""
    website = WebsiteFactory.create()
    old_key = f"sites/{website.name}/{UUID_PREFIX}_report.pdf"
    WebsiteContentFactory.create(website=website, file=old_key)
    # Reset flags after content creation (signals set them on save)
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )

    call_command("remove_uuid_from_filenames", filter=website.name, dry_run=True)

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


def test_dry_run_does_not_patch_video_metadata(mock_s3):
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

    call_command("remove_uuid_from_filenames", filter=website.name, dry_run=True)

    video_resource.refresh_from_db()
    assert video_resource.metadata["video_files"]["video_captions_file"] == captions_old


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
