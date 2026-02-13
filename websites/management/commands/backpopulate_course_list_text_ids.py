"""Backpopulate text_id field for course-list courses"""  # noqa: INP001

from django.db import transaction

from main.management.commands.filter import WebsiteFilterCommand
from websites import constants
from websites.api import fetch_website
from websites.models import Website, WebsiteContent


class Command(WebsiteFilterCommand):
    """
    Add text_id field to course-list course entries for efficient reference resolution.

    This command adds a 'text_id' field alongside the existing 'id' field in
    course-list metadata, enabling direct reference resolution without path parsing.
    """

    help = "Backpopulate text_id field for course-list courses"

    def add_arguments(self, parser, *args, **kwargs):
        """Add command arguments."""
        super().add_arguments(parser, *args, **kwargs)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):  # noqa: C901, PLR0912, PLR0915
        """Handle the management command execution."""
        super().handle(*args, **options)

        dry_run = options["dry_run"]
        verbosity = options["verbosity"]

        msg = "Backpopulating text_id for course-list course references"
        self.stdout.write(self.style.SUCCESS(msg))

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        website_qset = self.filter_websites(websites=Website.objects.all())

        # Find all course-lists content
        course_lists = WebsiteContent.objects.filter(
            website__in=website_qset,
            type=constants.CONTENT_TYPE_COURSE_LIST,
            metadata__isnull=False,
        )

        total_course_lists = course_lists.count()
        updated_count = 0
        skipped_count = 0

        if verbosity >= 1:
            self.stdout.write(f"Found {total_course_lists} course-lists to process")

        for course_list in course_lists:
            courses = course_list.metadata.get(
                constants.METADATA_FIELD_COURSE_LIST_COURSES, []
            )

            if not courses:
                continue

            needs_update = False
            updated_courses = []

            for course_entry in courses:
                if not isinstance(course_entry, dict) or "id" not in course_entry:
                    updated_courses.append(course_entry)
                    continue

                # Check if text_id already exists
                if "text_id" in course_entry:
                    updated_courses.append(course_entry)
                    continue

                # Extract short_id from path like "courses/18-01-fall-2020"
                course_ref = course_entry["id"]
                normalized = course_ref.strip().strip("/")
                short_id = (
                    normalized.split("/")[-1] if "/" in normalized else normalized
                )

                if not short_id:
                    if verbosity >= 2:  # noqa: PLR2004
                        msg = "  Skipping empty reference in "
                        msg += course_list.text_id
                        self.stdout.write(self.style.WARNING(msg))
                    updated_courses.append(course_entry)
                    continue

                try:
                    # Find the website by short_id
                    website = fetch_website(short_id)

                    # Find the website-listing content for this course
                    listing = WebsiteContent.objects.filter(
                        website_id=course_list.website_id,
                        type=constants.CONTENT_TYPE_WEBSITE,
                        filename=website.short_id,
                    ).first()

                    if listing:
                        # Add text_id alongside existing id
                        updated_entry = {**course_entry, "text_id": listing.text_id}
                        updated_courses.append(updated_entry)
                        needs_update = True

                        if verbosity >= 2:  # noqa: PLR2004
                            msg = "  Added text_id for "
                            msg += f"{course_entry['id']} → {listing.text_id}"
                            self.stdout.write(msg)
                    else:
                        if verbosity >= 2:  # noqa: PLR2004
                            msg = f"  No listing for course {short_id} "
                            msg += f"in {course_list.text_id}"
                            self.stdout.write(self.style.WARNING(msg))
                        updated_courses.append(course_entry)

                except Website.DoesNotExist:
                    if verbosity >= 2:  # noqa: PLR2004
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Website not found for short_id: {short_id}"
                            )
                        )
                    updated_courses.append(course_entry)

            if needs_update:
                if not dry_run:
                    with transaction.atomic():
                        field = constants.METADATA_FIELD_COURSE_LIST_COURSES
                        course_list.metadata[field] = updated_courses
                        course_list.save(update_fields=["metadata"])

                updated_count += 1
                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Updated {course_list.text_id}")
                    )
            else:
                skipped_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN: Would have updated {updated_count} course-lists"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully updated {updated_count} course-lists"
                )
            )

        if skipped_count > 0:
            msg = f"  Skipped {skipped_count} course-lists "
            msg += "(already up-to-date or empty)"
            self.stdout.write(msg)
