"""Backpopulate referencing content"""  # noqa: INP001

from django.db import transaction
from mitol.common.utils import now_in_utc

from main.management.commands.filter import WebsiteFilterCommand
from websites.models import Website, WebsiteContent
from websites.utils import resolve_referenced_content_ids

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
        content_references = self._collect_references(content_batch, verbosity)

        if not content_references:
            if verbosity >= 2:  # noqa: PLR2004
                self.stdout.write("No references found in this batch")
            return 0

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(
                f"Found references for {len(content_references)} content items in batch"
            )

        # Update relationships for this batch
        batch_updated = self._update_relationships(content_references, verbosity)

        if verbosity >= 2:  # noqa: PLR2004
            self.stdout.write(f"Updated {batch_updated} content items in batch")

        return batch_updated

    def _collect_references(self, content_batch, verbosity):
        """Collect resolved referenced content ids from a content batch."""
        content_references = {}

        for content in content_batch:
            if referenced_content_ids := resolve_referenced_content_ids(content):
                content_references[content.id] = referenced_content_ids

                if verbosity >= 3:  # noqa: PLR2004
                    self.stdout.write(
                        f"Content {content.text_id} references "
                        f"{len(referenced_content_ids)} items"
                    )

        return content_references

    def _update_relationships(self, content_references, verbosity):
        """Update content relationships in a transaction."""
        batch_updated = 0

        with transaction.atomic():
            for content_id, referenced_content_ids in content_references.items():
                try:
                    content = WebsiteContent.objects.get(id=content_id)

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
