"""Reconcile the "Open Textbooks" learning resource type to complete-textbook resources."""  # noqa: INP001, E501

import logging
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from websites.constants import (
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
)
from websites.models import Website, WebsiteContent

log = logging.getLogger(__name__)

OPEN_TEXTBOOK_LRT = "Open Textbooks"
LRT_FIELD = "learning_resource_types"
HAS_TAG_FILTER = {f"metadata__{LRT_FIELD}__contains": OPEN_TEXTBOOK_LRT}
BULK_UPDATE_BATCH_SIZE = 100


def strip_open_textbook(objects) -> list:
    """
    Remove OPEN_TEXTBOOK_LRT from each object's ``metadata[LRT_FIELD]`` list.

    ``objects`` is any iterable of objects exposing a ``.metadata`` dict (both
    ``WebsiteContent`` and ``Website``). Returns the objects as a list, ready for
    ``bulk_update(..., ["metadata"])`` and for collecting impacted website ids.
    """
    objects = list(objects)
    for obj in objects:
        learning_resource_types = obj.metadata.get(LRT_FIELD) or []
        obj.metadata = {
            **obj.metadata,
            LRT_FIELD: [
                lrt for lrt in learning_resource_types if lrt != OPEN_TEXTBOOK_LRT
            ],
        }
    return objects


def add_open_textbook(objects) -> list:
    """
    Add OPEN_TEXTBOOK_LRT to each object's ``metadata[LRT_FIELD]`` list if absent.

    Returns the objects as a list, ready for ``bulk_update(..., ["metadata"])`` and
    for collecting impacted website ids.
    """
    objects = list(objects)
    for obj in objects:
        metadata = obj.metadata if isinstance(obj.metadata, dict) else {}
        learning_resource_types = metadata.get(LRT_FIELD) or []
        if OPEN_TEXTBOOK_LRT not in learning_resource_types:
            obj.metadata = {
                **metadata,
                LRT_FIELD: [*learning_resource_types, OPEN_TEXTBOOK_LRT],
            }
    return objects


class Command(BaseCommand):
    """Reconcile the "Open Textbooks" learning resource type to a set of complete-textbook resources."""  # noqa: E501

    help = __doc__

    def add_arguments(self, parser):
        """Register the --textbook-uuids option."""
        parser.add_argument(
            "--textbook-uuids",
            dest="textbook_uuids",
            required=True,
            help=(
                "Comma-separated resource text_ids (UUIDs) for the complete-textbook "
                'PDFs that should carry the "Open Textbooks" tag. The tag is removed '
                "from everything else and from all Website.metadata, and added to "
                "these resources and their courses' sitemetadata."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Reconcile the tag to the textbook set and mark impacted sites dirty."""
        textbook_uuids = {
            uuid.strip()
            for uuid in (options["textbook_uuids"] or "").split(",")
            if uuid.strip()
        }

        # Validate the keep-list up front so a bad input never mutates data.
        textbook_resources = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_RESOURCE, text_id__in=textbook_uuids
        )
        missing = sorted(
            textbook_uuids - set(textbook_resources.values_list("text_id", flat=True))
        )
        if missing:
            msg = f"No resource found for textbook UUID(s): {', '.join(missing)}"
            raise CommandError(msg)
        match_count = textbook_resources.count()
        if match_count != len(textbook_uuids):
            msg = (
                f"{len(textbook_uuids)} textbook UUID(s) matched {match_count} "
                "resources — a UUID resolves to more than one resource "
                "(text_id is unique per site, not globally). Resolve the ambiguity "
                "and retry."
            )
            raise CommandError(msg)
        textbook_website_ids = set(
            textbook_resources.values_list("website_id", flat=True)
        )

        with transaction.atomic():
            # 1. Strip the tag from every Website and WebsiteContent that has it.
            stripped_content = strip_open_textbook(
                WebsiteContent.objects.filter(**HAS_TAG_FILTER)
            )
            WebsiteContent.objects.bulk_update(
                stripped_content, ["metadata"], batch_size=BULK_UPDATE_BATCH_SIZE
            )
            stripped_websites = strip_open_textbook(
                Website.objects.filter(**HAS_TAG_FILTER)
            )
            Website.objects.bulk_update(
                stripped_websites, ["metadata"], batch_size=BULK_UPDATE_BATCH_SIZE
            )

            # 2. Add the tag to the textbook resources and their sitemetadata.
            #    (Re-fetched so they reflect the strip above. Website.metadata is
            #    intentionally not re-tagged — it is strip-only.)
            tagged_content = add_open_textbook(
                [
                    *textbook_resources,
                    *WebsiteContent.objects.filter(
                        type=CONTENT_TYPE_METADATA,
                        website_id__in=textbook_website_ids,
                    ),
                ]
            )
            WebsiteContent.objects.bulk_update(
                tagged_content, ["metadata"], batch_size=BULK_UPDATE_BATCH_SIZE
            )

            # 3. Mark every touched site dirty. This is a best-effort superset:
            #    every site that actually changed is flagged, and a few that only
            #    saw no-op writes (e.g. a textbook already tagged) may be too.
            impacted_website_ids = {content.website_id for content in stripped_content}
            impacted_website_ids |= {website.uuid for website in stripped_websites}
            impacted_website_ids |= {content.website_id for content in tagged_content}
            Website.objects.filter(uuid__in=impacted_website_ids).update(
                has_unpublished_live=True,
                has_unpublished_draft=True,
            )

        self._log_summary(
            stripped_content, stripped_websites, tagged_content, impacted_website_ids
        )

    def _log_summary(
        self, stripped_content, stripped_websites, tagged_content, impacted_website_ids
    ):
        """Log per-type counts and the impacted sites for later selective publish."""
        removed_by_type = Counter(content.type for content in stripped_content)
        # Names (the publish identifier) of impacted sites, logged so the run can
        # be followed by a targeted republish of exactly these sites.
        impacted_names = sorted(
            Website.objects.filter(uuid__in=impacted_website_ids).values_list(
                "name", flat=True
            )
        )
        log.info(
            'Reconciled "%s": %d site(s) impacted and marked for republish: %s',
            OPEN_TEXTBOOK_LRT,
            len(impacted_names),
            ", ".join(impacted_names),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'"{OPEN_TEXTBOOK_LRT}" reconciliation complete:\n'
                f"  removed from {removed_by_type[CONTENT_TYPE_PAGE]} pages, "
                f"{removed_by_type[CONTENT_TYPE_RESOURCE]} resources, "
                f"{removed_by_type[CONTENT_TYPE_METADATA]} sitemetadata content, "
                f"{len(stripped_websites)} Website.metadata records\n"
                f"  ensured on {len(tagged_content)} textbook resource/sitemetadata item(s)\n"  # noqa: E501
                f"  {len(impacted_names)} site(s) marked as having unpublished changes"
            )
        )
