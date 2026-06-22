"""Tests for the reconcile_open_textbook_lrt management command."""  # noqa: INP001

import logging
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from websites.constants import (
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.reconcile_open_textbook_lrt import (
    LRT_FIELD,
    OPEN_TEXTBOOK_LRT,
    add_open_textbook,
    strip_open_textbook,
)
from websites.models import Website

pytestmark = pytest.mark.django_db

# An unrelated metadata key the command must never touch. Seeded into every
# object below so tests can assert reconciliation leaves other keys intact.
OTHER_KEY = "title"
OTHER_VALUE = "Unrelated metadata"


def create_content(website, content_type, learning_resource_types, **kwargs):
    """Create a WebsiteContent with the given learning_resource_types list."""
    return WebsiteContentFactory.create(
        website=website,
        type=content_type,
        metadata={LRT_FIELD: list(learning_resource_types), OTHER_KEY: OTHER_VALUE},
        **kwargs,
    )


def assert_unrelated_metadata_preserved(*objects):
    """Assert the command left each (already-refreshed) object's other keys intact."""
    for obj in objects:
        assert obj.metadata[OTHER_KEY] == OTHER_VALUE


def reset_dirty_flags(website):
    """Clear dirty flags without triggering WebsiteContent.save() side effects."""
    Website.objects.filter(pk=website.pk).update(
        has_unpublished_live=False, has_unpublished_draft=False
    )


def run_command(textbook_uuids):
    """Invoke the command, returning captured stdout."""
    out = StringIO()
    call_command(
        "reconcile_open_textbook_lrt", textbook_uuids=textbook_uuids, stdout=out
    )
    return out.getvalue()


# ---------------------------------------------------------------------------
# Unit tests for the strip/add helpers
# ---------------------------------------------------------------------------


def test_strip_removes_tag_and_preserves_other_lrts():
    """strip_open_textbook drops only Open Textbooks, keeping other LRTs."""
    objects = [
        SimpleNamespace(
            metadata={
                LRT_FIELD: [OPEN_TEXTBOOK_LRT, "Readings"],
                OTHER_KEY: OTHER_VALUE,
            }
        )
    ]
    result = strip_open_textbook(objects)
    assert result[0].metadata[LRT_FIELD] == ["Readings"]
    assert result[0].metadata[OTHER_KEY] == OTHER_VALUE  # unrelated key untouched


def test_add_appends_tag_when_absent():
    """add_open_textbook appends the tag when missing."""
    objects = [
        SimpleNamespace(metadata={LRT_FIELD: ["Readings"], OTHER_KEY: OTHER_VALUE})
    ]
    result = add_open_textbook(objects)
    assert result[0].metadata[LRT_FIELD] == ["Readings", OPEN_TEXTBOOK_LRT]
    assert result[0].metadata[OTHER_KEY] == OTHER_VALUE  # unrelated key untouched


def test_add_is_noop_when_already_present():
    """add_open_textbook does not duplicate an existing tag."""
    objects = [
        SimpleNamespace(
            metadata={LRT_FIELD: [OPEN_TEXTBOOK_LRT], OTHER_KEY: OTHER_VALUE}
        )
    ]
    result = add_open_textbook(objects)
    assert result[0].metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]
    assert result[0].metadata[OTHER_KEY] == OTHER_VALUE  # unrelated key untouched


def test_add_handles_missing_field():
    """add_open_textbook creates the LRT list when it is absent."""
    objects = [SimpleNamespace(metadata={OTHER_KEY: OTHER_VALUE})]
    result = add_open_textbook(objects)
    assert result[0].metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]
    assert result[0].metadata[OTHER_KEY] == OTHER_VALUE  # unrelated key untouched


def test_add_handles_none_metadata():
    """add_open_textbook tolerates a null metadata value."""
    objects = [SimpleNamespace(metadata=None)]
    result = add_open_textbook(objects)
    assert result[0].metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]


# ---------------------------------------------------------------------------
# Input validation (runs before any data is mutated)
# ---------------------------------------------------------------------------


def test_unmatched_uuid_raises_error():
    """A UUID that matches no resource aborts the command."""
    with pytest.raises(CommandError, match="No resource found"):
        run_command("does-not-exist")


def test_uuid_matching_multiple_resources_raises_error():
    """A UUID resolving to resources in more than one site aborts the command."""
    site_a = WebsiteFactory.create()
    site_b = WebsiteFactory.create()
    create_content(site_a, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT], text_id="dup")
    create_content(site_b, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT], text_id="dup")
    with pytest.raises(CommandError, match="matched 2 resources"):
        run_command("dup")


def test_validation_failure_makes_no_changes():
    """A failed validation leaves existing tags untouched."""
    website = WebsiteFactory.create()
    page = create_content(website, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT])
    with pytest.raises(CommandError):
        run_command("does-not-exist")
    page.refresh_from_db()
    assert page.metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]  # unchanged


def test_duplicate_and_whitespace_uuids_are_deduped():
    """Repeated UUIDs (and surrounding whitespace) are deduped, not a count error."""
    website = WebsiteFactory.create()
    textbook = create_content(website, CONTENT_TYPE_RESOURCE, ["Readings"])
    run_command(f" {textbook.text_id}, {textbook.text_id} ")  # same UUID twice
    textbook.refresh_from_db()
    assert textbook.metadata[LRT_FIELD] == ["Readings", OPEN_TEXTBOOK_LRT]


# ---------------------------------------------------------------------------
# Pages and non-textbook resources are stripped
# ---------------------------------------------------------------------------


def test_strips_tag_from_page():
    """Pages always lose the tag (they are never textbooks)."""
    website = WebsiteFactory.create()
    page = create_content(website, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT, "Readings"])
    run_command("")
    page.refresh_from_db()
    assert page.metadata[LRT_FIELD] == ["Readings"]
    assert_unrelated_metadata_preserved(page)


def test_keeps_textbook_resource_and_strips_other_resource():
    """A textbook resource keeps the tag; a non-textbook resource loses it."""
    website = WebsiteFactory.create()
    textbook = create_content(website, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    excerpt = create_content(website, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    run_command(textbook.text_id)
    textbook.refresh_from_db()
    excerpt.refresh_from_db()
    assert textbook.metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]
    assert excerpt.metadata[LRT_FIELD] == []
    assert_unrelated_metadata_preserved(textbook, excerpt)


def test_adds_tag_to_untagged_textbook_resource():
    """A textbook resource that lacks the tag gains it."""
    website = WebsiteFactory.create()
    textbook = create_content(website, CONTENT_TYPE_RESOURCE, ["Readings"])
    run_command(textbook.text_id)
    textbook.refresh_from_db()
    assert textbook.metadata[LRT_FIELD] == ["Readings", OPEN_TEXTBOOK_LRT]
    assert_unrelated_metadata_preserved(textbook)


def test_removes_only_open_textbook_from_multi_lrt_resource():
    """Only Open Textbooks is removed; other LRTs are left untouched."""
    website = WebsiteFactory.create()
    resource = create_content(
        website,
        CONTENT_TYPE_RESOURCE,
        ["Readings", OPEN_TEXTBOOK_LRT, "Lecture Notes"],
    )
    run_command("")
    resource.refresh_from_db()
    assert resource.metadata[LRT_FIELD] == ["Readings", "Lecture Notes"]
    assert_unrelated_metadata_preserved(resource)


# ---------------------------------------------------------------------------
# Course level — sitemetadata reconciled, Website.metadata strip-only
# ---------------------------------------------------------------------------


def test_strips_course_level_for_textbookless_course():
    """A course with no textbook loses the tag from sitemetadata and Website.metadata."""
    website = WebsiteFactory.create(
        metadata={LRT_FIELD: [OPEN_TEXTBOOK_LRT, "Exams"], OTHER_KEY: OTHER_VALUE}
    )
    sitemeta = create_content(
        website, CONTENT_TYPE_METADATA, [OPEN_TEXTBOOK_LRT, "Exams"]
    )
    run_command("")  # no textbook resources -> course has no full textbook
    sitemeta.refresh_from_db()
    website.refresh_from_db()
    assert sitemeta.metadata[LRT_FIELD] == ["Exams"]
    assert website.metadata[LRT_FIELD] == ["Exams"]
    assert_unrelated_metadata_preserved(sitemeta, website)


def test_textbook_course_adds_to_sitemetadata_but_not_website_metadata():
    """A textbook course gains the tag on sitemetadata but never on Website.metadata."""
    website = WebsiteFactory.create(
        metadata={LRT_FIELD: ["Exams"], OTHER_KEY: OTHER_VALUE}
    )
    textbook = create_content(website, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    sitemeta = create_content(website, CONTENT_TYPE_METADATA, ["Exams"])
    run_command(textbook.text_id)
    sitemeta.refresh_from_db()
    website.refresh_from_db()
    assert OPEN_TEXTBOOK_LRT in sitemeta.metadata[LRT_FIELD]  # added
    assert OPEN_TEXTBOOK_LRT not in website.metadata[LRT_FIELD]  # never added
    assert_unrelated_metadata_preserved(sitemeta, website)


def test_textbook_course_strips_website_metadata_even_when_sitemetadata_tagged():
    """Website.metadata is strip-only: a textbook course loses it there but keeps it
    on the sitemetadata content.
    """
    website = WebsiteFactory.create(
        metadata={LRT_FIELD: [OPEN_TEXTBOOK_LRT], OTHER_KEY: OTHER_VALUE}
    )
    textbook = create_content(website, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    sitemeta = create_content(website, CONTENT_TYPE_METADATA, [OPEN_TEXTBOOK_LRT])
    run_command(textbook.text_id)
    website.refresh_from_db()
    sitemeta.refresh_from_db()
    assert website.metadata[LRT_FIELD] == []  # stripped, never re-added
    assert sitemeta.metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]  # retained
    assert_unrelated_metadata_preserved(website, sitemeta)


# ---------------------------------------------------------------------------
# Dirty flags and impacted-site logging
# ---------------------------------------------------------------------------


def test_marks_affected_site_dirty():
    """A site whose content changed is marked as having unpublished changes."""
    website = WebsiteFactory.create()
    create_content(website, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT])
    reset_dirty_flags(website)
    run_command("")
    website.refresh_from_db()
    assert website.has_unpublished_live is True
    assert website.has_unpublished_draft is True


def test_site_without_tag_not_dirtied():
    """A site with no Open Textbooks tag anywhere is left clean."""
    website = WebsiteFactory.create()
    create_content(website, CONTENT_TYPE_RESOURCE, ["Readings"])
    reset_dirty_flags(website)
    run_command("")
    website.refresh_from_db()
    assert website.has_unpublished_live is False
    assert website.has_unpublished_draft is False


def test_logs_impacted_sites_for_selective_publish(caplog):
    """Impacted site names are logged so they can be republished afterward."""
    website = WebsiteFactory.create()
    create_content(website, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT])
    with caplog.at_level(logging.INFO):
        run_command("")
    assert "impacted" in caplog.text
    assert website.name in caplog.text


def test_summary_reports_per_type_counts():
    """The stdout summary reports how many of each content type were stripped."""
    website = WebsiteFactory.create()
    create_content(website, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT])
    create_content(website, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])  # excerpt
    output = run_command("")
    assert "reconciliation complete" in output
    assert "1 pages" in output
    assert "1 resources" in output
    assert "1 site(s)" in output


# ---------------------------------------------------------------------------
# Cross-site integration — the realistic many-courses scenario
# ---------------------------------------------------------------------------


def test_reconciles_across_multiple_sites():
    """Several textbooks across several courses reconcile independently and correctly."""
    # Course A: a textbook (tagged) + an excerpt (tagged) + sitemetadata (untagged)
    # + Website.metadata (tagged).
    course_a = WebsiteFactory.create(
        metadata={LRT_FIELD: [OPEN_TEXTBOOK_LRT], OTHER_KEY: OTHER_VALUE}
    )
    textbook_a = create_content(course_a, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    excerpt_a = create_content(course_a, CONTENT_TYPE_RESOURCE, [OPEN_TEXTBOOK_LRT])
    sitemeta_a = create_content(course_a, CONTENT_TYPE_METADATA, ["Exams"])
    # Course B: a textbook missing the tag + sitemetadata already tagged.
    course_b = WebsiteFactory.create(metadata={LRT_FIELD: [], OTHER_KEY: OTHER_VALUE})
    textbook_b = create_content(course_b, CONTENT_TYPE_RESOURCE, ["Readings"])
    sitemeta_b = create_content(course_b, CONTENT_TYPE_METADATA, [OPEN_TEXTBOOK_LRT])
    # Course C: no textbook — fully stripped.
    course_c = WebsiteFactory.create(
        metadata={LRT_FIELD: [OPEN_TEXTBOOK_LRT], OTHER_KEY: OTHER_VALUE}
    )
    page_c = create_content(course_c, CONTENT_TYPE_PAGE, [OPEN_TEXTBOOK_LRT])
    sitemeta_c = create_content(course_c, CONTENT_TYPE_METADATA, [OPEN_TEXTBOOK_LRT])

    run_command(f"{textbook_a.text_id},{textbook_b.text_id}")

    for obj in (
        textbook_a,
        excerpt_a,
        sitemeta_a,
        course_a,
        textbook_b,
        sitemeta_b,
        page_c,
        sitemeta_c,
        course_c,
    ):
        obj.refresh_from_db()

    # Course A: textbook kept, excerpt stripped, sitemetadata gains it,
    # Website.metadata stripped.
    assert textbook_a.metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]
    assert excerpt_a.metadata[LRT_FIELD] == []
    assert sitemeta_a.metadata[LRT_FIELD] == ["Exams", OPEN_TEXTBOOK_LRT]
    assert course_a.metadata[LRT_FIELD] == []
    # Course B: textbook gains it, sitemetadata retains it.
    assert textbook_b.metadata[LRT_FIELD] == ["Readings", OPEN_TEXTBOOK_LRT]
    assert sitemeta_b.metadata[LRT_FIELD] == [OPEN_TEXTBOOK_LRT]
    # Course C: everything stripped.
    assert page_c.metadata[LRT_FIELD] == []
    assert sitemeta_c.metadata[LRT_FIELD] == []
    assert course_c.metadata[LRT_FIELD] == []
    # Every object's unrelated metadata key survived reconciliation.
    assert_unrelated_metadata_preserved(
        textbook_a,
        excerpt_a,
        sitemeta_a,
        course_a,
        textbook_b,
        sitemeta_b,
        page_c,
        sitemeta_c,
        course_c,
    )
