"""Tests for website migration 0075 — convert scalar _resource to list and rename to plural."""

import importlib

import pytest
from django.apps import apps

from websites.factories import WebsiteContentFactory, WebsiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def migration_module():
    """Import the migration module (names with leading digits need importlib)."""
    return importlib.import_module(
        "websites.migrations.0075_remove_video_file_path_fields"
    )


def test_migration_0075_converts_scalar_and_renames_to_plural(migration_module):
    """Scalar _resource content is converted to list and field is renamed to _resources."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website,
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": "caption-uuid-123",
                    "website": website.name,
                },
                "video_transcript_resource": {
                    "content": "transcript-uuid-456",
                    "website": website.name,
                },
            },
        },
    )

    migration_module._convert_and_rename(apps, None)  # noqa: SLF001

    content.refresh_from_db()
    vf = content.metadata["video_files"]

    # Old singular fields removed
    assert "video_captions_resource" not in vf
    assert "video_transcript_resource" not in vf

    # New plural fields with list content
    assert vf["video_captions_resources"]["content"] == ["caption-uuid-123"]
    assert vf["video_captions_resources"]["website"] == website.name
    assert vf["video_transcript_resources"]["content"] == ["transcript-uuid-456"]
    assert vf["video_transcript_resources"]["website"] == website.name


def test_migration_0075_renames_already_list_fields(migration_module):
    """Fields already in list format are renamed without content modification."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website,
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resource": {
                    "content": ["uuid-1", "uuid-2"],
                    "website": website.name,
                },
            },
        },
    )

    migration_module._convert_and_rename(apps, None)  # noqa: SLF001

    content.refresh_from_db()
    vf = content.metadata["video_files"]

    assert "video_captions_resource" not in vf
    assert vf["video_captions_resources"]["content"] == ["uuid-1", "uuid-2"]


def test_migration_0075_reverse_renames_to_singular_and_converts_to_scalar(
    migration_module,
):
    """Reverse migration renames _resources back to _resource and collapses list to scalar."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website,
        metadata={
            "resourcetype": "Video",
            "video_files": {
                "video_captions_resources": {
                    "content": ["uuid-1", "uuid-2"],
                    "website": website.name,
                },
                "video_transcript_resources": {
                    "content": ["uuid-3"],
                    "website": website.name,
                },
            },
        },
    )

    migration_module._reverse_rename_and_convert(apps, None)  # noqa: SLF001

    content.refresh_from_db()
    vf = content.metadata["video_files"]

    assert "video_captions_resources" not in vf
    assert "video_transcript_resources" not in vf
    # First element only
    assert vf["video_captions_resource"]["content"] == "uuid-1"
    assert vf["video_transcript_resource"]["content"] == "uuid-3"


def test_migration_0075_skips_content_without_video_files(migration_module):
    """Content without video_files metadata is silently skipped."""
    WebsiteContentFactory.create(metadata={"resourcetype": "Page"})
    # Should not raise
    migration_module._convert_and_rename(apps, None)  # noqa: SLF001
