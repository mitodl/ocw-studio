"""Tests for the content selected by batch repair commands."""  # noqa: INP001

import csv
from base64 import b64encode
from contextlib import closing
from functools import partial
from http import HTTPStatus
from io import BytesIO, StringIO
from threading import Thread
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import OperationalError, connection, transaction
from django.db.models.signals import pre_save
from django.test import TestCase
from github import GithubException

from content_sync import api
from content_sync.apis.github import GithubApiWrapper
from content_sync.backends.github import GithubBackend
from content_sync.constants import GIT_DATA_FILEPATH
from content_sync.management.utils import sync_repaired_content
from content_sync.repair import collect_repaired_content
from content_sync.serializers import serialize_content_to_file
from content_sync.tasks import sync_unsynced_websites
from content_sync.utils import get_destination_filepath
from gdrive_sync.factories import DriveFileFactory
from videos.constants import DESTINATION_ARCHIVE
from videos.factories import VideoFactory, VideoFileFactory
from videos.tasks import populate_video_file_size
from websites.constants import (
    CONTENT_TYPE_EXTERNAL_RESOURCE,
    CONTENT_TYPE_RESOURCE,
    PUBLISH_STATUS_PENDING,
    RESOURCE_TYPE_IMAGE,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig


def _run_repair(*args, **options):
    with TestCase.captureOnCommitCallbacks(execute=True):
        call_command(*args, **options)


def _mark_synced(content):
    state = content.content_sync_state
    state.synced_checksum = state.current_checksum
    state.data = {
        GIT_DATA_FILEPATH: get_destination_filepath(
            content, SiteConfig(content.website.starter.config)
        )
    }
    state.save(update_fields=["synced_checksum", "data"])


@pytest.fixture
def sync_task(db, settings, mocker):
    """Enable backend sync and capture the queued content IDs."""
    settings.CONTENT_SYNC_BACKEND = "content_sync.backends.github.GithubBackend"
    return mocker.patch("content_sync.tasks.sync_unsynced_websites.delay")


@pytest.fixture
def committed_content(django_db_setup, django_db_blocker):
    """Give two connections a committed row without flushing migration seed data."""
    with django_db_blocker.unblock():
        site = WebsiteFactory.build(owner=None, starter=None)
        Website.objects.bulk_create([site])
        try:
            yield WebsiteContentFactory.create(
                website=site, type=CONTENT_TYPE_RESOURCE, markdown="Repair value"
            )
        finally:
            site.delete()


def test_repair_locks_only_the_content_write(committed_content, mocker):
    """Observe the competing editor before, during, and after the repair's write."""
    content = committed_content
    write = content._do_update  # noqa: SLF001
    upsert = api.upsert_content_sync_state
    lock_sql = "SELECT id FROM websites_websitecontent WHERE id = %s FOR UPDATE NOWAIT"

    with closing(connection.copy()) as other, other.cursor() as editor:
        editor.execute("SET lock_timeout = '2s'")

        def edit_before_write(**_kwargs):
            editor.execute(
                "UPDATE websites_websitecontent SET markdown = %s WHERE id = %s",
                ["Editor value", content.pk],
            )

        def check_lock_during_write(*args, **kwargs):
            with pytest.raises(OperationalError, match="could not obtain lock"):
                editor.execute(lock_sql, [content.pk])
            return write(*args, **kwargs)

        def check_lock_after_write(instance):
            editor.execute(lock_sql, [content.pk])
            return upsert(instance)

        mocker.patch.object(content, "_do_update", side_effect=check_lock_during_write)
        mocker.patch.object(
            api, "upsert_content_sync_state", side_effect=check_lock_after_write
        )
        with collect_repaired_content() as repair:
            pre_save.connect(edit_before_write, sender=WebsiteContent)
            try:
                content.save()
            finally:
                pre_save.disconnect(edit_before_write, sender=WebsiteContent)

    content.refresh_from_db()
    assert content.markdown == "Repair value"
    assert repair.prepare_sync() == [content.pk]


def test_failed_write_leaves_a_pending_edit_out_of_scope(committed_content):
    """A write that timed out on a row lock has nothing of its own to sync."""
    content = committed_content
    assert not content.content_sync_state.is_synced
    lock_sql = "SELECT id FROM websites_websitecontent WHERE id = %s FOR UPDATE"

    with (
        closing(connection.copy()) as other,
        other.cursor() as editor,
        connection.cursor() as command,
    ):
        editor.execute("BEGIN")
        editor.execute(lock_sql, [content.pk])
        command.execute("SET lock_timeout = '100ms'")
        try:
            with collect_repaired_content() as repair:
                content.markdown = "Blocked repair"
                with pytest.raises(OperationalError, match="lock timeout"):
                    content.save()
        finally:
            command.execute("RESET lock_timeout")
            editor.execute("ROLLBACK")

    content.refresh_from_db()
    assert content.markdown == "Repair value"
    assert repair.prepare_sync() == []


def test_save_from_another_thread_stays_out_of_scope(committed_content):
    """Another thread writes on its own connection, so the write is not the repair's."""
    errors = []

    def edit():
        try:
            content = WebsiteContent.objects.get(pk=committed_content.pk)
            content.markdown = "Another thread"
            content.save()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    with collect_repaired_content() as repair:
        thread = Thread(target=edit)
        thread.start()
        thread.join()

    assert not errors
    committed_content.refresh_from_db()
    assert committed_content.markdown == "Another thread"
    assert repair.prepare_sync() == []


def test_unchanged_save_with_stale_sync_checksum_leaves_an_empty_scope(sync_task):
    """Refreshing a checksum left stale by a bulk edit is not a content repair."""
    content = WebsiteContentFactory.create(markdown="Original")
    WebsiteContent.objects.filter(pk=content.pk).update(markdown="Earlier bulk edit")
    content.refresh_from_db()
    checksum = content.calculate_checksum()
    assert content.content_sync_state.current_checksum != checksum

    with (
        TestCase.captureOnCommitCallbacks(execute=True),
        sync_repaired_content(StringIO(), enabled=True),
    ):
        content.save()

    content.content_sync_state.refresh_from_db()
    assert content.content_sync_state.current_checksum == checksum
    sync_task.assert_called_once_with(create_backends=True, content_ids=[])


@pytest.mark.parametrize(
    ("update_fields", "repair_metadata"),
    [(None, {}), (["metadata"], {}), (["metadata"], {"repaired": True})],
    ids=["unchanged-full-save", "unchanged-partial-save", "changed-partial-save"],
)
def test_sync_scope_with_a_concurrent_edit(
    update_fields, repair_metadata, sync_task, mocker
):
    """Select a row only when the repair's own SQL write changed its content."""
    content = WebsiteContentFactory.create(markdown="Original", metadata={})
    content.metadata = repair_metadata
    if update_fields:
        content.markdown = "Unsaved on the repair instance"

    upsert = api.upsert_content_sync_state

    def upsert_after_edit(instance):
        # Reproduce the other writer's SQL at the point its commit becomes visible.
        WebsiteContent.objects.filter(pk=instance.pk).update(markdown="Concurrent edit")
        return upsert(instance)

    mocker.patch.object(api, "upsert_content_sync_state", side_effect=upsert_after_edit)
    with (
        TestCase.captureOnCommitCallbacks(execute=True),
        sync_repaired_content(StringIO(), enabled=True),
    ):
        content.save(update_fields=update_fields)

    content.refresh_from_db()
    assert content.markdown == "Concurrent edit"
    assert content.metadata == repair_metadata
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[content.pk] if repair_metadata else []
    )


def test_new_content_saved_twice_is_synced(sync_task):
    """A second save must not make a row created by the repair look unchanged."""
    with (
        TestCase.captureOnCommitCallbacks(execute=True),
        sync_repaired_content(StringIO(), enabled=True),
    ):
        content = WebsiteContentFactory.create()
        content.save()
    sync_task.assert_called_once_with(create_backends=True, content_ids=[content.pk])


def test_reverted_and_rolled_back_writes_leave_an_empty_scope(sync_task):
    """Transient changes must not pull pre-existing dirty content into the sync."""
    reverted = WebsiteContentFactory.create(markdown="Original")
    rolled_back = WebsiteContentFactory.create()
    with (
        TestCase.captureOnCommitCallbacks(execute=True),
        sync_repaired_content(StringIO(), enabled=True),
    ):
        reverted.markdown = "Temporary"
        reverted.save()
        reverted.markdown = "Original"
        reverted.save()
        with transaction.atomic():
            rolled_back.markdown = "Temporary"
            rolled_back.save()
            transaction.set_rollback(True)
    sync_task.assert_called_once_with(create_backends=True, content_ids=[])


def test_reverted_write_includes_a_synced_intermediate_version(committed_content):
    """Git can record the temporary value after the first write releases its lock."""
    content = committed_content
    original = content.markdown
    with collect_repaired_content() as repair:
        content.markdown = "Temporary repair"
        content.save()
        with closing(connection.copy()) as other, other.cursor() as backend:
            backend.execute(
                "UPDATE content_sync_contentsyncstate SET synced_checksum = current_checksum "
                "WHERE content_id = %s RETURNING synced_checksum",
                [content.pk],
            )
            assert backend.fetchone() == (content.calculate_checksum(),)
        content.markdown = original
        content.save()

    assert repair.prepare_sync() == [content.pk]


@pytest.mark.parametrize(
    ("alias", "old_path"),
    [
        ("broken_metadata_link_fix", "/old/section/handout"),
        ("metadata_relative_urls", "resource/handout"),
    ],
)
def test_markdown_cleanup_syncs_target_of_repaired_metadata_url(
    alias, old_path, sync_task
):
    """A filtered metadata repair can introduce a plain link to a never-synced resource."""
    site = WebsiteFactory.create()
    page = WebsiteContentFactory.create(
        website=site,
        metadata={"description": f"[Handout]({old_path}#details)"},
    )
    target = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        dirpath="content/resource",
        filename="handout",
        is_page_content=True,
    )
    WebsiteContentFactory.create(text_id=target.text_id)

    _run_repair("markdown_cleanup", alias, filter=site.name, limit=1, commit=True)

    page.refresh_from_db()
    assert (
        page.metadata["description"]
        == f"[Handout](/{site.url_path}/resource/handout#details)"
    )
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[page.pk, target.pk]
    )


@pytest.mark.parametrize("edit", ["rename", "bulk_rename", "title"])
def test_markdown_cleanup_syncs_plain_url_target_only_when_git_path_changed(
    sync_task, edit
):
    """A previously synced target needs a new Git file at the URL emitted by the rule."""
    site = WebsiteFactory.create()
    page = WebsiteContentFactory.create(
        website=site, metadata={"description": "[Handout](/old/section/handout)"}
    )
    target = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        dirpath="content/resource",
        filename="handout" if edit == "title" else "old-handout",
        is_page_content=True,
    )
    _mark_synced(target)
    old_path = target.content_sync_state.data[GIT_DATA_FILEPATH]
    if edit == "bulk_rename":
        WebsiteContent.objects.filter(pk=target.pk).update(filename="handout")
    else:
        target.filename = "handout"
        target.title = "An earlier edit"
        target.save()

    _run_repair(
        "markdown_cleanup",
        "broken_metadata_link_fix",
        filter=site.name,
        limit=1,
        commit=True,
    )

    page.refresh_from_db()
    assert (
        page.metadata["description"] == f"[Handout](/{site.url_path}/resource/handout)"
    )
    target.content_sync_state.refresh_from_db()
    assert target.content_sync_state.data[GIT_DATA_FILEPATH] == old_path
    if edit == "title":
        sync_task.assert_called_once_with(create_backends=True, content_ids=[page.pk])
    else:
        assert not target.content_sync_state.is_synced
        sync_task.assert_called_once_with(
            create_backends=True, content_ids=[page.pk, target.pk]
        )


@pytest.mark.parametrize("lookup", ["missing", "present", "error"])
def test_markdown_cleanup_checks_destination_of_imported_target(
    sync_task, mocker, settings, lookup
):
    """An imported target needs syncing only if its newly referenced file is missing."""
    site = WebsiteFactory.create()
    page = WebsiteContentFactory.create(
        website=site, metadata={"description": "[Handout](/legacy/handout)"}
    )
    path = "content/resource/handout.md"
    imported_path = "content/resource/old-handout.md" if lookup == "missing" else path
    git = mocker.patch("content_sync.backends.github.GithubApiWrapper").return_value
    git.get_repo.return_value.get_contents.return_value = mocker.Mock(
        type="file",
        path=imported_path,
        content=b64encode(
            f"---\nuid: {uuid4()}\ntitle: Handout\ncontent_type: resource\n---\n".encode()
        ),
    )
    (target_id,) = GithubBackend(site).sync_all_content_to_db(path=imported_path)
    target = WebsiteContent.objects.get(pk=target_id)
    assert target.content_sync_state.is_synced
    assert target.content_sync_state.data is None
    target.filename = "handout"
    target.title = "An earlier edit"
    target.save()

    get_contents = git.git.get_repo.return_value.get_contents
    if lookup == "present":
        get_contents.return_value.type = "file"
    else:
        status = (
            HTTPStatus.NOT_FOUND
            if lookup == "missing"
            else HTTPStatus.INTERNAL_SERVER_ERROR
        )
        get_contents.side_effect = GithubException(status=status, data={}, headers={})
    run_cleanup = partial(
        _run_repair,
        "markdown_cleanup",
        "broken_metadata_link_fix",
        filter=site.name,
        limit=1,
        commit=True,
    )
    if lookup == "error":
        # Guessing here could sync the handout's unrelated pending edit.
        with pytest.raises(GithubException):
            run_cleanup()
        sync_task.assert_not_called()
        target.content_sync_state.refresh_from_db()
        assert target.content_sync_state.synced_checksum is not None
        return
    run_cleanup()

    page.refresh_from_db()
    assert (
        page.metadata["description"] == f"[Handout](/{site.url_path}/resource/handout)"
    )
    get_contents.assert_called_once_with(path, ref=settings.GIT_BRANCH_MAIN)
    sync_task.assert_called_once_with(
        create_backends=True,
        content_ids=[page.pk, target.pk] if lookup == "missing" else [page.pk],
    )


def test_markdown_cleanup_syncs_target_whose_url_prefixes_an_existing_link(sync_task):
    """An existing link to handout-solutions must not hide the new link to handout."""
    site = WebsiteFactory.create()
    page = WebsiteContentFactory.create(
        website=site,
        metadata={
            "description": (
                "[Handout](/legacy/handout) "
                f"[Solutions](/{site.url_path}/resource/handout-solutions)"
            )
        },
    )
    handout, _ = [
        WebsiteContentFactory.create(
            website=site,
            type=CONTENT_TYPE_RESOURCE,
            dirpath="content/resource",
            filename=name,
            is_page_content=True,
        )
        for name in ("handout", "handout-solutions")
    ]

    _run_repair(
        "markdown_cleanup",
        "broken_metadata_link_fix",
        filter=site.name,
        limit=1,
        commit=True,
    )

    page.refresh_from_db()
    description = page.metadata["description"]
    assert f"[Handout](/{site.url_path}/resource/handout)" in description
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[page.pk, handout.pk]
    )


def test_markdown_cleanup_syncs_target_of_a_link_with_an_empty_label(sync_task):
    """The generated resource_link has an empty title and still names its target."""
    site = WebsiteFactory.create()
    page = WebsiteContentFactory.create(website=site, markdown="[](/legacy/handout)")
    handout = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        dirpath="content/resource",
        filename="handout",
        is_page_content=True,
    )

    _run_repair(
        "markdown_cleanup",
        "broken_markdown_link_fix",
        filter=site.name,
        limit=1,
        commit=True,
    )

    page.refresh_from_db()
    assert page.markdown == f'{{{{% resource_link "{handout.text_id}" "" %}}}}'
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[page.pk, handout.pk]
    )


@pytest.mark.parametrize("metadata", [True, False], ids=["metadata", "markdown"])
def test_markdown_cleanup_syncs_only_emitted_nested_references(sync_task, metadata):
    """The outer link is repaired while its image label keeps the legacy URL."""
    site = WebsiteFactory.create()
    original = "[![Preview](/legacy/thumbnail)](/legacy/handout)"
    page = WebsiteContentFactory.create(website=site)
    thumbnail, handout = [
        WebsiteContentFactory.create(
            website=site,
            type=CONTENT_TYPE_RESOURCE,
            dirpath="content/resource",
            filename=name,
            is_page_content=True,
        )
        for name in ("thumbnail", "handout")
    ]
    # An existing reference elsewhere must not make the discarded one look new.
    page.markdown = f'{original}\n{{{{< resource uuid="{thumbnail.text_id}" >}}}}'
    page.metadata = {
        "description": f"{original}\n![Preview](/{site.url_path}/resource/thumbnail)"
    }
    page.save()
    alias = "broken_metadata_link_fix" if metadata else "broken_markdown_link_fix"
    _run_repair("markdown_cleanup", alias, filter=site.name, limit=1, commit=True)

    page.refresh_from_db()
    saved = page.metadata["description"] if metadata else page.markdown
    assert "![Preview](/legacy/thumbnail)" in saved
    assert (
        f"/{site.url_path}/resource/handout" if metadata else handout.text_id
    ) in saved
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[page.pk, handout.pk]
    )


@pytest.mark.parametrize(
    ("alias", "fields"),
    [
        (
            "link_to_external_resource",
            {
                "markdown": "[old](https://example.org/old) [new](https://example.org/new)"
            },
        ),
        (
            "nav_item_to_external_resource",
            {
                "metadata": {
                    "leftnav": [
                        {
                            "identifier": "external-old",
                            "url": "https://example.org/old",
                        },
                        {
                            "identifier": "external-new",
                            "url": "https://example.org/new",
                        },
                    ]
                }
            },
        ),
    ],
)
@pytest.mark.parametrize("previously_synced", [False, True])
def test_markdown_cleanup_syncs_source_and_required_resources(  # noqa: PLR0913, PLR0917
    alias, fields, previously_synced, settings, mocker, sync_task
):
    """New references need their targets in Git, including reused resources."""
    mocker.patch("external_resources.signals.submit_url_to_wayback_task.delay")
    folder = "content/external-resources"
    starter = WebsiteStarterFactory.create(
        config={
            "collections": [{"name": CONTENT_TYPE_EXTERNAL_RESOURCE, "folder": folder}]
        }
    )
    settings.OCW_COURSE_STARTER_SLUG = starter.slug
    website = WebsiteFactory.create(starter=starter)
    WebsiteContentFactory.create(website__starter=starter, **fields)
    source = WebsiteContentFactory.create(website=website, **fields)
    WebsiteContentFactory.create(website=website, **fields)
    reused = WebsiteContentFactory.create(
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        dirpath=folder,
        metadata={
            "external_url": "https://example.org/old",
            "has_external_license_warning": False,
        },
    )
    reused.referencing_content.add(source)
    if previously_synced:
        state = reused.content_sync_state
        state.synced_checksum = state.current_checksum
        state.save(update_fields=["synced_checksum"])
        reused.title = "An earlier edit"
        reused.save()

    options = {"commit": True, "limit": 1, "filter": website.name}
    _run_repair("markdown_cleanup", alias, **options)
    new = WebsiteContent.objects.get(
        website=website, metadata__external_url="https://example.org/new"
    )
    expected_ids = (
        [source.pk, new.pk] if previously_synced else [source.pk, reused.pk, new.pk]
    )
    sync_task.assert_called_once_with(create_backends=True, content_ids=expected_ids)

    sync_task.reset_mock()
    _run_repair("markdown_cleanup", alias, **options)
    sync_task.assert_called_once_with(create_backends=True, content_ids=[])


def test_markdown_cleanup_uses_the_site_of_a_repaired_plain_url(sync_task):
    """A cross-site URL identifies its own target even when the source has the same UUID."""
    source_site = WebsiteFactory.create()
    target = WebsiteContentFactory.create(
        type=CONTENT_TYPE_RESOURCE,
        dirpath="content/resource/handout",
        filename="_index",
    )
    path = f"/{target.website.url_path}/resource/handout"
    page = WebsiteContentFactory.create(
        website=source_site, metadata={"description": f"[Handout]({path}/_index)"}
    )
    WebsiteContentFactory.create(website=source_site, text_id=target.text_id)

    _run_repair(
        "markdown_cleanup",
        "broken_metadata_link_fix",
        filter=source_site.name,
        limit=1,
        commit=True,
    )

    page.refresh_from_db()
    assert page.metadata["description"] == f"[Handout]({path})"
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[target.pk, page.pk]
    )


def test_markdown_cleanup_syncs_only_new_gallery_references_on_the_same_site(sync_task):
    """The same UUID on another site and existing page references stay out."""
    site = WebsiteFactory.create()
    image = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        metadata={"resourcetype": RESOURCE_TYPE_IMAGE},
    )
    WebsiteContentFactory.create(text_id=image.text_id)
    existing = WebsiteContentFactory.create(website=site)
    filename = image.text_id.replace("-", "") + "_image.jpg"
    page = WebsiteContentFactory.create(
        website=site,
        markdown=(
            f'{{{{< image-gallery-item href="{filename}" >}}}}\n'
            f'{{{{% resource_link "{existing.text_id}" "Existing" %}}}}'
        ),
    )

    _run_repair(
        "markdown_cleanup", "image_gallery_item_uuid", filter=site.name, commit=True
    )

    page.refresh_from_db()
    assert f'uuid="{image.text_id}"' in page.markdown
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[image.pk, page.pk]
    )


@pytest.mark.parametrize(
    ("commit", "skip_sync"), [(True, False), (False, False), (True, True)]
)
def test_fix_file_urls_syncs_only_saved_paths(
    commit, skip_sync, sync_task, mocker, tmp_path
):
    """Report every candidate, syncing only verified paths saved in commit mode."""
    website = WebsiteFactory.create()
    repaired = WebsiteContentFactory.create(
        website=website, type=CONTENT_TYPE_RESOURCE, file="courses/found.pdf"
    )
    missing = WebsiteContentFactory.create(
        website=website, type=CONTENT_TYPE_RESOURCE, file="courses/missing.pdf"
    )
    WebsiteContentFactory.create(type=CONTENT_TYPE_RESOURCE, file="courses/found.pdf")
    bucket = mocker.patch(
        "websites.management.commands.fix_file_urls.get_boto3_resource"
    ).return_value.Bucket.return_value
    new_path = f"courses/{website.name}/found.pdf"
    bucket.objects.filter.side_effect = lambda *, Prefix: (
        [new_path] if Prefix == new_path else []
    )
    report = tmp_path / "paths.csv"
    _run_repair(
        "fix_file_urls",
        prefix="courses",
        filter=website.short_id,
        commit=commit,
        skip_sync=skip_sync,
        out=str(report),
    )

    repaired.refresh_from_db()
    assert repaired.file.name == (new_path if commit else "courses/found.pdf")
    with report.open() as input_file:
        assert {
            row["content"]: row["exists"] for row in csv.DictReader(input_file)
        } == {repaired.text_id: "True", missing.text_id: "False"}
    if commit and not skip_sync:
        sync_task.assert_called_once_with(
            create_backends=True, content_ids=[repaired.pk]
        )
        sync_task.reset_mock()
        _run_repair(
            "fix_file_urls", prefix="courses", filter=website.short_id, commit=True
        )
        sync_task.assert_called_once_with(create_backends=True, content_ids=[])
    else:
        sync_task.assert_not_called()


@pytest.mark.parametrize(
    ("field", "pending_edit"),
    [("video_captions_resources", False), ("video_transcript_resources", True)],
)
def test_fix_file_urls_syncs_videos_with_changed_published_paths(
    field, pending_edit, sync_task, mocker
):
    """Only linked videos in the same site need their front matter regenerated."""
    site = WebsiteFactory.create(name="test-course", url_path="courses/test-course")
    resource = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        file="courses/lecture.pdf",
        dirpath="content/resource",
        filename="lecture_pdf",
        is_page_content=True,
    )
    metadata = {
        "resourcetype": "Video",
        "video_files": {
            field: {
                "content": [resource.text_id] if pending_edit else resource.text_id,
                "website": site.name,
            }
        },
    }
    video = WebsiteContentFactory.create(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        metadata=metadata,
        dirpath="content/resource",
        filename="video",
        is_page_content=True,
    )
    _mark_synced(video)
    if pending_edit:
        video.title = "Pending video edit"
        video.save()
    other_site_video = WebsiteContentFactory.create(
        type=CONTENT_TYPE_RESOURCE, is_page_content=True, metadata=metadata
    )
    _mark_synced(other_site_video)
    config = SiteConfig(site.starter.config)
    assert "/courses/lecture.pdf" in serialize_content_to_file(config, video)
    bucket = mocker.patch(
        "websites.management.commands.fix_file_urls.get_boto3_resource"
    ).return_value.Bucket.return_value
    bucket.objects.filter.return_value = ["courses/test-course/lecture.pdf"]

    _run_repair("fix_file_urls", prefix="courses", filter=site.name, commit=True)

    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[resource.pk, video.pk]
    )
    video.refresh_from_db()
    assert "/courses/test-course/lecture.pdf" in serialize_content_to_file(
        config, video
    )
    assert not video.content_sync_state.is_synced
    assert (
        video.content_sync_state.data[GIT_DATA_FILEPATH] == "content/resource/video.md"
    )
    other_site_video.content_sync_state.refresh_from_db()
    assert other_site_video.content_sync_state.is_synced

    mocker.patch("content_sync.apis.github.Github")
    mocker.patch("content_sync.apis.github.get_token")
    backend = GithubApiWrapper(site)
    commit = mocker.patch.object(backend, "commit_tree")
    backend.upsert_content_files(
        query_set=WebsiteContent.objects.filter(
            pk__in=sync_task.call_args.kwargs["content_ids"]
        )
    )
    elements, _ = commit.call_args.args
    blobs = [element._identity for element in elements]  # noqa: SLF001
    files = {blob["path"]: blob["content"] for blob in blobs}
    assert "/courses/test-course/lecture.pdf" in files["content/resource/video.md"]

    sync_task.reset_mock()
    _run_repair("fix_file_urls", prefix="courses", filter=site.name, commit=True)
    sync_task.assert_called_once_with(create_backends=True, content_ids=[])


def test_backpopulate_video_downloads_syncs_writes_before_a_caught_error(
    sync_task, mocker
):
    """An S3 move alone is insufficient, but a saved 3Play transcript belongs in the repair."""
    website = WebsiteFactory.create(starter__slug="ocw-course-v2")
    video = VideoFactory.create(website=website)
    resource = WebsiteContentFactory.build(
        website=website,
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"source": "youtube", "youtube_id": "yt1"},
            "video_files": {},
        },
    )
    resource.skip_sync = True
    resource.save()
    DriveFileFactory.create(website=website, video=video, resource=resource)
    VideoFileFactory.create(
        video=video, destination=DESTINATION_ARCHIVE, s3_key="original/a_360p_16_9.mp4"
    )
    without_resource = VideoFactory.create(website=website)
    VideoFileFactory.create(
        video=without_resource,
        destination=DESTINATION_ARCHIVE,
        s3_key="original/b_360p_16_9.mp4",
    )
    VideoFactory.create(website=website)
    WebsiteContentFactory.create(website=website)
    mocker.patch("videos.api.move_s3_object")
    mocker.patch("videos.api.get_boto3_resource")
    mocker.patch("videos.api.fetch_content_file_size", return_value=123)
    threeplay = mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": [{"status": "complete", "id": 11, "media_file_id": 22}]},
    )
    mocker.patch(
        "videos.threeplay_sync.fetch_file",
        side_effect=[BytesIO(b"transcript"), ValueError("caption unavailable")],
    )
    mocker.patch(
        "videos.threeplay_sync.upload_to_s3",
        return_value=f"/courses/{website.name}/yt1_transcript.pdf",
    )

    stderr = StringIO()
    _run_repair("backpopulate_video_downloads", filter=website.name, stderr=stderr)

    assert "caption unavailable" in stderr.getvalue()
    assert without_resource.source_key in stderr.getvalue()
    transcript = WebsiteContent.objects.get(
        website=website, filename="yt1_transcript_pdf"
    )
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[resource.pk, transcript.pk]
    )

    threeplay.return_value = {"data": []}
    sync_task.reset_mock()
    _run_repair("backpopulate_video_downloads", filter=website.name)
    sync_task.assert_called_once_with(create_backends=True, content_ids=[])


@pytest.mark.parametrize(
    ("initial_size", "archive_size", "skip_sync", "expected_change"),
    [
        (50, 200, False, True),
        (100, 200, False, True),
        (100, 100, False, False),
        (200, 200, False, False),
        (100, 200, True, False),
    ],
    ids=["both-change", "worker-only", "no-change", "worker-reverts", "skip-sync"],
)
def test_backpopulate_waits_for_worker_before_git_sync(  # noqa: PLR0913, PLR0917
    initial_size, archive_size, skip_sync, expected_change, sync_task, mocker
):
    """The only Git write includes the final size, even if the worker finishes last."""
    site = WebsiteFactory.create()
    resource = _archive_video(site, "lecture", initial_size)
    mocker.patch("videos.api.get_boto3_resource")
    mocker.patch("videos.api.fetch_content_file_size", return_value=100)
    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        side_effect=ValueError("3Play unavailable"),
    )
    mocker.patch(
        "videos.tasks.requests.head",
        return_value=mocker.Mock(
            status_code=HTTPStatus.OK, headers={"Content-Length": str(archive_size)}
        ),
    )
    # Hold the worker until its result is requested, as if the command won the race.
    result = mocker.Mock()

    def submit(args, kwargs, **_options):
        result.get.side_effect = lambda **_: populate_video_file_size.run(
            *args, **kwargs
        )
        return result

    queued = mocker.patch.object(
        populate_video_file_size, "apply_async", side_effect=submit
    )
    mocker.patch("content_sync.apis.github.Github")
    mocker.patch("content_sync.apis.github.get_token")
    backend = GithubBackend(site)
    mocker.patch.object(api, "get_sync_backend", return_value=backend)
    mocker.patch.object(backend, "create_website_in_backend")
    commit = mocker.patch.object(backend.api, "commit_tree")

    def run_sync(**kwargs):
        sync_unsynced_websites.run(**kwargs)
        return mocker.Mock()

    sync_task.side_effect = run_sync
    stderr = StringIO()
    _run_repair(
        "backpopulate_video_downloads",
        filter=site.name,
        skip_sync=skip_sync,
        stderr=stderr,
    )
    assert "3Play unavailable" in stderr.getvalue()
    queued.assert_called_once()
    if skip_sync:
        result.get.assert_not_called()
        result.get()  # Deliver the ordinary background size update.
        sync_task.assert_not_called()
    else:
        result.get.assert_called_once_with(propagate=False)
        sync_task.assert_called_once_with(
            create_backends=True, content_ids=[resource.pk] if expected_change else []
        )
    if expected_change:
        commit.assert_called_once()
        (element,), _ = commit.call_args.args
        assert f"file_size: {archive_size}\n" in element._identity["content"]  # noqa: SLF001
    else:
        commit.assert_not_called()
    resource.refresh_from_db()
    assert resource.metadata["file_size"] == archive_size


def _archive_video(site, filename, size):
    video = VideoFactory.create(website=site)
    key = f"{site.s3_path}/{filename}_360p_16_9.mp4".strip("/")
    resource = WebsiteContentFactory.build(
        website=site,
        type=CONTENT_TYPE_RESOURCE,
        file=key,
        dirpath="content/resource",
        filename=filename,
        is_page_content=True,
        metadata={
            "resourcetype": "Video",
            "video_metadata": {"source": "youtube", "youtube_id": "video-1"},
            "video_files": {"archive_url": f"https://example.org/{filename}.mp4"},
            "file_size": size,
        },
    )
    resource.skip_sync = True
    resource.save()
    DriveFileFactory.create(website=site, video=video, resource=resource)
    VideoFileFactory.create(video=video, destination=DESTINATION_ARCHIVE, s3_key=key)
    return resource


@pytest.mark.parametrize(
    "propagate", [False, True], ids=["failed-result", "eager-exception"]
)
def test_failed_archive_worker_preserves_other_repairs(
    sync_task, mocker, caplog, monkeypatch, propagate
):
    """Keep a command write made before a failed lookup and another worker's change."""
    site = WebsiteFactory.create()
    monkeypatch.setattr(
        populate_video_file_size.app.conf, "CELERY_TASK_EAGER_PROPAGATES", propagate
    )
    failed = _archive_video(site, "failed", 50)
    updated = _archive_video(site, "updated", 100)
    mocker.patch("videos.api.get_boto3_resource")
    mocker.patch("videos.api.fetch_content_file_size", return_value=100)
    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": []},
    )

    def head(url, **_kwargs):
        if url.endswith("failed.mp4"):
            return mocker.Mock(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        return mocker.Mock(status_code=HTTPStatus.OK, headers={"Content-Length": "200"})

    mocker.patch("videos.tasks.requests.head", side_effect=head)
    _run_repair("backpopulate_video_downloads", filter=site.name)
    failed.refresh_from_db()
    updated.refresh_from_db()
    assert failed.metadata["file_size"] == 100
    assert updated.metadata["file_size"] == 200
    assert f"deferred task for content {failed.pk}" in caplog.text
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[failed.pk, updated.pk]
    )


@pytest.mark.parametrize("rolled_back", [True, False])
def test_video_save_queues_its_size_check_only_when_committed(
    sync_task, mocker, rolled_back
):
    """A size check for a rolled-back save would run against a write that never was."""
    resource = WebsiteContent.objects.get(
        pk=_archive_video(WebsiteFactory.create(), "lecture", 100).pk
    )
    mocker.patch(
        "videos.threeplay_sync.threeplay_transcript_api_request",
        return_value={"data": []},
    )
    queued = mocker.patch.object(populate_video_file_size, "apply_async")
    queued.return_value.get.return_value = None
    with (
        TestCase.captureOnCommitCallbacks(execute=True),
        sync_repaired_content(StringIO(), enabled=True),
        transaction.atomic(),
    ):
        resource.title = "Edited"
        resource.save()
        transaction.set_rollback(rolled_back)

    assert queued.call_count == (0 if rolled_back else 1)
    sync_task.assert_called_once_with(
        create_backends=True, content_ids=[] if rolled_back else [resource.pk]
    )


@pytest.mark.parametrize("archive_changed", [False, True])
def test_archive_worker_preserves_metadata_edited_during_request(
    archive_changed, sync_task, mocker
):
    """Apply the response to the requested archive while preserving newer metadata."""
    archive_url = "https://example.org/video.mp4"
    resource = WebsiteContentFactory.create(
        metadata={"video_files": {"archive_url": archive_url}}
    )

    def head(url, **_kwargs):
        assert url == archive_url
        resource.metadata["description"] = "Edited during HEAD"
        if archive_changed:
            resource.metadata["video_files"]["archive_url"] = (
                "https://example.org/other.mp4"
            )
        resource.save(update_fields=["metadata"])
        Website.objects.filter(pk=resource.website_id).update(
            live_publish_status=PUBLISH_STATUS_PENDING, latest_build_id_live=12345
        )
        return mocker.Mock(status_code=HTTPStatus.OK, headers={"Content-Length": "200"})

    mocker.patch("videos.tasks.requests.head", side_effect=head)
    mocker.patch.object(api, "get_sync_backend")
    sync_task.side_effect = sync_unsynced_websites.run
    with TestCase.captureOnCommitCallbacks(execute=True):
        checksum = populate_video_file_size.run(resource.pk, report_change=True)

    resource.refresh_from_db()
    assert resource.metadata["description"] == "Edited during HEAD"
    sync_task.assert_not_called()
    assert resource.website.live_publish_status == PUBLISH_STATUS_PENDING
    assert resource.website.latest_build_id_live == 12345
    if archive_changed:
        assert "file_size" not in resource.metadata
        assert checksum is None
    else:
        assert resource.metadata["file_size"] == 200
        assert checksum == resource.calculate_checksum()
