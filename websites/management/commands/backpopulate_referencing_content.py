"""Backpopulate referencing content"""  # noqa: INP001

from django.db import transaction
from mitol.common.utils import now_in_utc

from main.management.commands.filter import WebsiteFilterCommand
from websites import constants
from websites.models import Website, WebsiteContent
from websites.utils import compile_referencing_content

BATCH_SIZE_DEFAULT = 500  # Default batch size for processing content


class Command(WebsiteFilterCommand):
    """Backpopulate referencing content for existing resources"""

    help = "Backpopulate referencing content for existing resources"

    def add_arguments(self, parser, *args, **kwargs):
        """Add command arguments."""
        super().add_arguments(parser, *args, **kwargs)
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE_DEFAULT,
            help="Number of content items to process in each batch (default: )",
        )

    def handle(self, *args, **options):
        """Handle the management command execution."""
        super().handle(*args, **options)

        batch_size = options["batch_size"] or BATCH_SIZE_DEFAULT
        verbosity = options["verbosity"]

        self.stdout.write("Backpopulating referencing content for existing resources")
        start = now_in_utc()

        website_qset = self.filter_websites(websites=Website.objects.all())

        # Get total count for progress tracking
        total_content = WebsiteContent.objects.filter(website__in=website_qset).count()
        self.stdout.write(
            f"Processing {total_content} content items in batches of {batch_size}..."
        )

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(
                f"Website filter applied: {website_qset.count()} websites"
            )

        total_updated = 0
        offset = 0

        while offset < total_content:
            if verbosity >= 1:
                self.stdout.write(
                    f"Processing batch {offset // batch_size + 1}: "
                    f"items {offset + 1} to {min(offset + batch_size, total_content)}"
                )

            batch_updated = self._process_batch(
                website_qset, offset, batch_size, verbosity
            )
            total_updated += batch_updated
            offset += batch_size

            # Progress update
            processed = min(offset, total_content)
            if verbosity >= 1:
                self.stdout.write(
                    f"Processed {processed}/{total_content} items "
                    f"({processed / total_content * 100:.1f}%) - "
                    f"{batch_updated} updated in this batch"
                )

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            f"Backpopulate referencing content finished, "
            f"took {total_seconds:.2f} seconds"
        )
        self.stdout.write(
            f"{website_qset.count()} websites processed, "
            f"{total_updated} content updated"
        )

    def _process_batch(self, website_qset, offset, batch_size, verbosity):
        """Process a batch of content items."""
        # Fetch a batch of content
        content_batch = WebsiteContent.objects.filter(website__in=website_qset)[
            offset : offset + batch_size
        ]

        if verbosity >= 3:  # noqa: PLR2004
            self.stdout.write(f"Fetched {len(content_batch)} content items for batch")

        # Collect references for this batch only
        content_references, all_reference_uuids = self._collect_references(
            content_batch, verbosity
        )

        if not all_reference_uuids:
            if verbosity >= 2:  # noqa: PLR2004
                self.stdout.write("No references found in this batch")
            return 0

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(
                f"Found {len(all_reference_uuids)} unique references in batch"
            )

        # Bulk fetch all referenced content for this batch
        referenced_content_map = self._fetch_referenced_content(
            all_reference_uuids, verbosity
        )

        # Update relationships for this batch
        batch_updated = self._update_relationships(
            content_references, referenced_content_map, verbosity
        )

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(f"Updated {batch_updated} content items in batch")

        return batch_updated

    def _collect_references(self, content_batch, verbosity):
        """Collect and flatten references from content batch."""
        content_references = {}
        all_reference_uuids = set()

        for content in content_batch:
            if references := compile_referencing_content(content):
                content_references[content.id] = references
                all_reference_uuids.update(references)

                if verbosity >= 3:  # noqa: PLR2004
                    self.stdout.write(
                        f"Content {content.text_id} references {len(references)} items"
                    )

        return content_references, all_reference_uuids

    def _fetch_referenced_content(self, all_reference_uuids, verbosity):
        """Fetch referenced content in bulk, resolving path-like references."""
        referenced_content_map = {
            content.text_id: content
            for content in WebsiteContent.objects.filter(
                text_id__in=all_reference_uuids
            ).only("id", "text_id")
        }

        # Handle path-like references (e.g., "courses/test-course" for hidden courses)
        unresolved = set(all_reference_uuids) - set(referenced_content_map.keys())
        path_like_refs = [ref for ref in unresolved if "/" in ref]

        if path_like_refs and verbosity >= 3:  # noqa: PLR2004
            self.stdout.write(f"Resolving {len(path_like_refs)} path-like references")

        for path_ref in path_like_refs:
            # Try to find website by url_path
            try:
                normalized_path = path_ref.strip().strip("/")
                website = Website.objects.get(url_path=normalized_path)
                # Find representative content from this website (prefer sitemetadata)
                representative = (
                    WebsiteContent.objects.filter(
                        website=website, type=constants.CONTENT_TYPE_METADATA
                    )
                    .only("id", "text_id")
                    .first()
                )
                if representative:
                    referenced_content_map[path_ref] = representative
                    if verbosity >= 3:  # noqa: PLR2004
                        msg = (
                            f"Resolved {path_ref} → "
                            f"{representative.text_id} (sitemetadata)"
                        )
                        self.stdout.write(msg)
            except Website.DoesNotExist:
                if verbosity >= 3:  # noqa: PLR2004
                    self.stdout.write(f"Could not resolve path reference: {path_ref}")

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(
                f"Resolved {len(referenced_content_map)} of "
                f"{len(all_reference_uuids)} references"
            )

        return referenced_content_map

    def _update_relationships(
        self, content_references, referenced_content_map, verbosity
    ):
        """Update content relationships in a transaction."""
        batch_updated = 0

        with transaction.atomic():
            for content_id, reference_uuids in content_references.items():
                try:
                    content = WebsiteContent.objects.get(id=content_id)

                    # Get valid referenced content objects
                    referenced_content_ids = [
                        referenced_content_map[ref_uuid].id
                        for ref_uuid in reference_uuids
                        if ref_uuid in referenced_content_map
                    ]

                    referenced_content_ids = list(set(referenced_content_ids))

                    if referenced_content_ids:
                        referenced_objects = WebsiteContent.objects.filter(
                            id__in=referenced_content_ids
                        )
                        content.referenced_by.set(referenced_objects)
                        batch_updated += 1

                        if verbosity >= 3:  # noqa: PLR2004
                            self.stdout.write(
                                f"Updated {content.text_id} with "
                                f"{len(referenced_content_ids)} references"
                            )

                except WebsiteContent.DoesNotExist:
                    # Content might have been deleted between queries
                    if verbosity >= 2:  # noqa: PLR2004
                        self.stdout.write(
                            f"Content with id {content_id} not found, skipping"
                        )
                    continue

        return batch_updated
