"""Backpopulate referencing content"""  # noqa: INP001

from django.db import transaction
from mitol.common.utils import now_in_utc

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website, WebsiteContent
from websites.utils import compile_referencing_content


class Command(WebsiteFilterCommand):
    """Backpopulate referencing content for existing resources"""

    help = "Backpopulate referencing content for existing resources"

    def add_arguments(self, parser):
        """Add command arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=500,
            help="Number of content items to process in each chunk (default: 500)",
        )

    def handle(self, *args, **options):
        """Handle the management command execution."""
        super().handle(*args, **options)

        chunk_size = options["chunk_size"]
        verbosity = options["verbosity"]

        self.stdout.write("Backpopulating referencing content for existing resources")
        start = now_in_utc()

        website_qset = self.filter_websites(websites=Website.objects.all())

        # Get total count for progress tracking
        total_content = website_qset.count()
        self.stdout.write(
            f"Processing {total_content} content items in chunks of {chunk_size}..."
        )

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(f"Verbosity level: {verbosity}")
            self.stdout.write(
                f"Website filter applied: {website_qset.count()} websites"
            )

        total_updated = 0
        offset = 0

        while offset < total_content:
            if verbosity >= 1:
                self.stdout.write(
                    f"Processing chunk {offset // chunk_size + 1}: "
                    f"items {offset + 1} to {min(offset + chunk_size, total_content)}"
                )

            chunk_updated = self._process_chunk(
                website_qset, offset, chunk_size, verbosity
            )
            total_updated += chunk_updated
            offset += chunk_size

            # Progress update
            processed = min(offset, total_content)
            if verbosity >= 1:
                self.stdout.write(
                    f"Processed {processed}/{total_content} items "
                    f"({processed/total_content*100:.1f}%) - "
                    f"{chunk_updated} updated in this chunk"
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

    def _process_chunk(self, website_qset, offset, chunk_size, verbosity):
        """Process a chunk of content items."""
        # Fetch a chunk of content with optimized query
        content_chunk = WebsiteContent.objects.filter(website__in=website_qset)[
            offset : offset + chunk_size
        ]

        if verbosity >= 3:  # noqa: PLR2004
            self.stdout.write(f"Fetched {len(content_chunk)} content items for chunk")

        # Collect references for this chunk only
        content_references, all_reference_uuids = self._collect_references(
            content_chunk, verbosity
        )

        if not all_reference_uuids:
            if verbosity >= 2:  # noqa: PLR2004
                self.stdout.write("No references found in this chunk")
            return 0

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(
                f"Found {len(all_reference_uuids)} unique references in chunk"
            )

        # Bulk fetch all referenced content for this chunk
        referenced_content_map = self._fetch_referenced_content(
            all_reference_uuids, verbosity
        )

        # Update relationships for this chunk
        chunk_updated = self._update_relationships(
            content_references, referenced_content_map, verbosity
        )

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(f"Updated {chunk_updated} content items in chunk")

        return chunk_updated

    def _collect_references(self, content_chunk, verbosity):
        """Collect and flatten references from content chunk."""
        content_references = {}
        all_reference_uuids = set()

        for content in content_chunk:
            if references := compile_referencing_content(content):
                # Flatten the references list in case it contains nested lists
                flat_references = []
                for ref in references:
                    if isinstance(ref, list):
                        flat_references.extend(ref)
                    else:
                        flat_references.append(ref)

                content_references[content.id] = flat_references
                all_reference_uuids.update(flat_references)

                if verbosity >= 3:  # noqa: PLR2004
                    self.stdout.write(
                        f"Content {content.text_id} references "
                        f"{len(flat_references)} items"
                    )

        return content_references, all_reference_uuids

    def _fetch_referenced_content(self, all_reference_uuids, verbosity):
        """Fetch referenced content in bulk."""
        referenced_content_map = {
            content.text_id: content
            for content in WebsiteContent.objects.filter(
                text_id__in=all_reference_uuids
            ).only("id", "text_id")
        }

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
        chunk_updated = 0
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

                    if referenced_content_ids:
                        # Set new relationships (clears existing ones automatically)
                        referenced_objects = WebsiteContent.objects.filter(
                            id__in=referenced_content_ids
                        )
                        content.referenced_by.set(referenced_objects)
                        chunk_updated += 1

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

        return chunk_updated
