"""Tests for the fix_external_resource_urls management command."""  # noqa: INP001

import csv
from io import StringIO

import pytest
from django.core.management import call_command

from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE, CONTENT_TYPE_RESOURCE
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import Website

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_sync_task(mocker):
    """Mock the sync_website_content task used by the command."""
    mock_delay = mocker.patch(
        "websites.management.commands.fix_external_resource_urls"
        ".sync_website_content.delay"
    )
    mock_delay.return_value.get.return_value = None
    return mock_delay


def _reset_dirty_flags(website):
    """Content creation itself dirties the website via signals; reset for a clean assertion."""
    Website.objects.filter(uuid=website.uuid).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )


@pytest.mark.parametrize(
    ("label", "original_url", "expected_cleaned"),
    [
        (
            "trailing newline",
            "http://www.gutenberg.org/browse/BIBREC/BR6960.HTM\n",
            "http://www.gutenberg.org/browse/BIBREC/BR6960.HTM",
        ),
        (
            "leading newline",
            "\nhttp://books.google.com/books?id=K3V1juIGhXYC&pg=Pafrontcover",
            "http://books.google.com/books?id=K3V1juIGhXYC&pg=Pafrontcover",
        ),
        (
            "newline mid-URL",
            "http://books.google.com/books?\nid=TzJ2L9ZmlQUC&pg=PAfrontcover",
            "http://books.google.com/books?id=TzJ2L9ZmlQUC&pg=PAfrontcover",
        ),
    ],
)
def test_cleans_control_characters(
    mock_sync_task, label, original_url, expected_cleaned
):
    """Control characters are stripped regardless of where they appear in the URL."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": original_url},
    )

    call_command("fix_external_resource_urls", commit=True)

    content.refresh_from_db()
    assert content.metadata["external_url"] == expected_cleaned, label


def test_leaves_clean_url_untouched(mock_sync_task):
    """A URL with no control characters is left exactly as-is and not reported."""
    website = WebsiteFactory.create()
    clean_url = "http://books.google.com/books?id=CLEAN123&pg=Pafrontcover"
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": clean_url},
    )

    call_command("fix_external_resource_urls", commit=True)

    content.refresh_from_db()
    assert content.metadata["external_url"] == clean_url


def test_ignores_non_external_resource_content_type(mock_sync_task):
    """Only type=external-resource content is considered, even if another type has a similar field."""
    website = WebsiteFactory.create()
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={"external_url": "http://example.com/\n"},
    )

    call_command("fix_external_resource_urls", commit=True)

    content.refresh_from_db()
    assert content.metadata["external_url"] == "http://example.com/\n"


def test_ignores_missing_external_url(mock_sync_task):
    """Content with no external_url key in metadata is skipped without error."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"has_external_license_warning": False},
    )

    call_command("fix_external_resource_urls", commit=True)  # must not raise


def test_dry_run_makes_no_changes(mock_sync_task):
    """Without --commit, the database is not modified."""
    website = WebsiteFactory.create()
    original_url = "http://www.gutenberg.org/etext/4217\n"
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": original_url},
    )

    call_command("fix_external_resource_urls")

    content.refresh_from_db()
    assert content.metadata["external_url"] == original_url
    mock_sync_task.assert_not_called()


def test_dry_run_writes_csv_plan(tmp_path, mock_sync_task):
    """Even without --commit, the CSV plan reports what would change."""
    website = WebsiteFactory.create()
    original_url = "http://www.gutenberg.org/etext/98\n"
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": original_url},
    )
    output_file = tmp_path / "plan.csv"

    call_command("fix_external_resource_urls", out=str(output_file))

    assert output_file.exists()
    with output_file.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["pk_id"] == str(content.pk)
    assert rows[0]["text_id"] == str(content.text_id)
    assert rows[0]["website_name"] == website.name
    assert rows[0]["original_url"] == original_url
    assert rows[0]["cleaned_url"] == "http://www.gutenberg.org/etext/98"
    # dry run: DB itself is untouched even though the plan was written
    content.refresh_from_db()
    assert content.metadata["external_url"] == original_url


def test_dry_run_prints_affected_content_list(mock_sync_task):
    """Without --commit, the affected content prints to stdout for inspection (e.g. on production)."""
    website = WebsiteFactory.create()
    original_url = "http://www.gutenberg.org/etext/141\n"
    content = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": original_url},
    )
    out = StringIO()

    call_command("fix_external_resource_urls", stdout=out)

    output = out.getvalue()
    assert "pk_id,text_id,website_name,external_link" in output
    assert f"{content.pk},{content.text_id},{website.name},{original_url}" in output
    content.refresh_from_db()
    assert content.metadata["external_url"] == original_url


def test_dry_run_prints_nothing_when_no_content_affected(mock_sync_task):
    """When nothing is affected, no affected-content list is printed."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/already-clean"},
    )
    out = StringIO()

    call_command("fix_external_resource_urls", stdout=out)

    assert "pk_id,text_id,website_name,external_link" not in out.getvalue()


def test_filter_limits_to_specified_website(mock_sync_task):
    """The --filter argument restricts processing to the named website only."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    content_a = WebsiteContentFactory.create(
        website=website_a,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/a\n"},
    )
    content_b = WebsiteContentFactory.create(
        website=website_b,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/b\n"},
    )

    call_command("fix_external_resource_urls", commit=True, filter=website_a.name)

    content_a.refresh_from_db()
    content_b.refresh_from_db()
    assert content_a.metadata["external_url"] == "http://example.com/a"
    assert content_b.metadata["external_url"] == "http://example.com/b\n"


def test_marks_website_dirty_after_fix(mock_sync_task):
    """Saving the cleaned content marks the website as having unpublished changes.

    This exercises the real post_save -> ContentSyncState signal chain rather than
    assuming it fires (content_sync/signals.py:upsert_content_sync_state).
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://www.gutenberg.org/etext/6688\n"},
    )
    _reset_dirty_flags(website)

    call_command("fix_external_resource_urls", commit=True)

    website.refresh_from_db()
    assert website.has_unpublished_live is True
    assert website.has_unpublished_draft is True


def test_triggers_sync_when_committed(settings, mock_sync_task):
    """A committed run with affected content syncs that content's website."""
    # pytest overrides CONTENT_SYNC_BACKEND to "" globally (pyproject.toml) to keep
    # the suite from touching a real backend; restore a truthy value to exercise
    # the branch that's actually gated on it.
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://www.gutenberg.org/etext/768\n"},
    )

    call_command("fix_external_resource_urls", commit=True)

    mock_sync_task.assert_called_once_with(website.name)


def test_sync_scoped_to_affected_websites_only(settings, mock_sync_task):
    """A committed run only syncs websites it actually modified, not every unsynced site."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    affected_website = WebsiteFactory.create()
    unaffected_website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=affected_website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/bad\n"},
    )
    WebsiteContentFactory.create(
        website=unaffected_website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/already-clean"},
    )

    call_command("fix_external_resource_urls", commit=True)

    mock_sync_task.assert_called_once_with(affected_website.name)


def test_skip_sync_flag_prevents_sync(mock_sync_task):
    """--skip-sync prevents the sync_unsynced_websites task from running."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://www.jstor.org/stable/3985060\n"},
    )

    call_command("fix_external_resource_urls", commit=True, skip_sync=True)

    mock_sync_task.assert_not_called()


def test_no_sync_when_nothing_modified(mock_sync_task):
    """A committed run with no affected content does not trigger a sync."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        metadata={"external_url": "http://example.com/already-clean"},
    )

    call_command("fix_external_resource_urls", commit=True)

    mock_sync_task.assert_not_called()
