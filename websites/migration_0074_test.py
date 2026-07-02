"""Tests for website migration 0073 — back-populate _resource fields from file-path lookup"""

import importlib
import uuid

import pytest
from django.apps import apps

from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def migration_module():
    """Import the migration module (names with leading digits need importlib)."""
    return importlib.import_module(
        "websites.migrations.0074_video_caption_transcript_files_to_resources"
    )


def test_migration_0073_backpopulates_resource_fields_from_file_path(
    migration_module,
):
    """_resource fields are back-populated by matching the legacy _file path to WebsiteContent.file."""
    website = WebsiteFactory.create()

    captions_path = f"courses/{website.name}/abc_captions.vtt"
    transcript_path = f"courses/{website.name}/abc_transcript.pdf"

    captions = WebsiteContentFactory.create(
        website=website,
        filename="abc_captions_vtt",
        type="resource",
        file=captions_path,
    )
    transcript = WebsiteContentFactory.create(
        website=website,
        filename="abc_transcript_pdf",
        type="resource",
        file=transcript_path,
        metadata={"resourcetype": "Document"},
    )

    video = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": f"/{captions_path}",
                "video_transcript_file": f"/{transcript_path}",
            },
        },
    )

    migration_module._backpopulate_resource_fields(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    assert vf["video_captions_resource"]["content"] == str(captions.text_id)
    assert vf["video_captions_resource"]["website"] == website.name
    assert vf["video_transcript_resource"]["content"] == str(transcript.text_id)
    assert vf["video_transcript_resource"]["website"] == website.name
    # Legacy _file fields are removed once a resource is linked
    assert "video_captions_file" not in vf
    assert "video_transcript_file" not in vf


def test_migration_0073_preserves_orphan_file_fields_when_no_resource_found(
    migration_module,
):
    """Orphan _file paths (no matching WebsiteContent) are preserved, not deleted."""
    video = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_file": "/courses/site/captions.vtt",
                "video_transcript_file": "/courses/site/transcript.pdf",
            },
        }
    )

    migration_module._backpopulate_resource_fields(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    # Orphan paths must be kept so they can be remediated later
    assert vf["video_captions_file"] == "/courses/site/captions.vtt"
    assert vf["video_transcript_file"] == "/courses/site/transcript.pdf"
    assert "video_captions_resource" not in vf
    assert "video_transcript_resource" not in vf


def test_migration_0073_preserves_existing_resource_fields(migration_module):
    """Existing _resource values are left untouched when referenced_by is empty."""
    existing_id = str(uuid.uuid4())
    video = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": existing_id,
                    "website": "site",
                },
            },
        }
    )

    migration_module._backpopulate_resource_fields(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    assert vf["video_captions_resource"] == {
        "content": existing_id,
        "website": "site",
    }


def test_migration_0073_skips_non_video_content(migration_module):
    """Content without resourcetype=Video is not modified even if it has video_files."""
    content = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Document",
            "video_files": {
                "video_captions_file": "/some/path.vtt",
            },
        }
    )

    migration_module._backpopulate_resource_fields(apps, None)  # noqa: SLF001

    content.refresh_from_db()
    # Non-video content is untouched because the queryset filters to resourcetype=Video
    assert "video_captions_file" in content.metadata["video_files"]


# ---------------------------------------------------------------------------
# Reverse migration tests
# ---------------------------------------------------------------------------


def test_migration_0073_reverse_restores_file_field_from_resource(migration_module):
    """Reverse: text_id in _resource → file path written back to _file field."""
    website = WebsiteFactory.create()

    captions = WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=f"courses/{website.name}/abc_captions.vtt",
    )
    transcript = WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=f"courses/{website.name}/abc_transcript.pdf",
    )

    video = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": str(captions.text_id),
                    "website": website.name,
                },
                "video_transcript_resource": {
                    "content": str(transcript.text_id),
                    "website": website.name,
                },
            },
        },
    )

    migration_module._reverse_backpopulate(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    assert vf["video_captions_file"] == f"/courses/{website.name}/abc_captions.vtt"
    assert vf["video_transcript_file"] == f"/courses/{website.name}/abc_transcript.pdf"
    assert "video_captions_resource" not in vf
    assert "video_transcript_resource" not in vf


def test_migration_0073_reverse_uses_first_text_id_when_list(migration_module):
    """Reverse: when content is a list, only the first text_id is restored."""
    website = WebsiteFactory.create()

    captions = WebsiteContentFactory.create(
        website=website,
        type="resource",
        file=f"courses/{website.name}/caps_en.vtt",
    )

    video = WebsiteContentFactory.create(
        website=website,
        type="resource",
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": [str(captions.text_id), "other-id"],
                    "website": website.name,
                },
            },
        },
    )

    migration_module._reverse_backpopulate(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    assert vf["video_captions_file"] == f"/courses/{website.name}/caps_en.vtt"
    assert "video_captions_resource" not in vf


def test_migration_0073_reverse_removes_resource_field_when_no_matching_resource(
    migration_module,
):
    """Reverse: _resource field is removed even when the text_id has no match."""
    video = WebsiteContentFactory.create(
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": "nonexistent-id",
                    "website": "site",
                },
            },
        }
    )

    migration_module._reverse_backpopulate(apps, None)  # noqa: SLF001

    video.refresh_from_db()
    vf = video.metadata["video_files"]

    assert "video_captions_resource" not in vf
    assert "video_captions_file" not in vf
