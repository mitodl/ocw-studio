"""Management command to update YouTube video tags without re-uploading videos"""

from django.conf import settings
from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from videos.utils import get_course_tag, get_tags_with_course
from videos.youtube import YouTubeApi, is_youtube_enabled
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import WebsiteContent
from websites.utils import get_dict_field, set_dict_field

# Verbosity level for detailed output
VERBOSITY_DETAILED = 2


class Command(WebsiteFilterCommand):
    """Update YouTube video tags for existing videos without re-uploading"""

    help = "Update YouTube video tags for existing videos without re-uploading"

    def add_arguments(self, parser):
        """Add command-specific arguments"""
        super().add_arguments(parser, is_filter_required=False)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without actually updating YouTube",
        )
        parser.add_argument(
            "--youtube-id",
            dest="youtube_id",
            default=None,
            help="Update only the video with this specific YouTube ID",
        )
        parser.add_argument(
            "--add-course-tag",
            action="store_true",
            default=False,
            help="Automatically add course name (URL slug) as a tag",
        )

    def get_video_resources(self, youtube_id_filter):
        """
        Build and return the filtered queryset of video resources.

        Returns WebsiteContent objects (not Video model objects) that represent
        video resources with YouTube IDs.
        """
        query_id_field = f"metadata__{settings.YT_FIELD_ID.replace('.', '__')}"
        video_resources = WebsiteContent.objects.filter(
            Q(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
        ).exclude(Q(**{query_id_field: None}) | Q(**{query_id_field: ""}))

        video_resources = self.filter_website_contents(video_resources)

        if youtube_id_filter:
            video_resources = video_resources.filter(
                **{query_id_field: youtube_id_filter}
            )

        return video_resources

    def process_video(
        self, video_resource, youtube, dry_run, add_course_tag, verbosity
    ):
        """
        Process a single video resource to update its tags.

        Returns tuple: (status, message) where status is 'success', 'error', or 'skip'
        """
        youtube_id = get_dict_field(video_resource.metadata, settings.YT_FIELD_ID)
        course_slug = get_course_tag(video_resource.website)
        website_name = video_resource.website.name

        # Merge course slug into tags if requested
        if add_course_tag:
            merged_tags = get_tags_with_course(video_resource.metadata, course_slug)
            set_dict_field(video_resource.metadata, settings.YT_FIELD_TAGS, merged_tags)
            if not dry_run:
                video_resource.save()

        # Get tags after potential merge
        tags = get_dict_field(video_resource.metadata, settings.YT_FIELD_TAGS)

        # Display detailed info only at verbosity level 2+
        if verbosity >= VERBOSITY_DETAILED:
            tag_display = tags if tags else "(no tags)"
            self.stdout.write(f"\nProcessing: {video_resource.title} ({website_name})")
            self.stdout.write(f"  YouTube ID: {youtube_id}")
            self.stdout.write(f"  Tags: {tag_display}")
            if add_course_tag:
                self.stdout.write(f"  Course tag added: {course_slug}")

        if dry_run:
            return ("success", "  [DRY RUN] Would not update tags on YouTube")

        try:
            # Update only tags on YouTube (not other metadata)
            youtube.update_video_tags(youtube_id, tags or "")
        except Exception as exc:  # noqa: BLE001
            msg = f"Error updating tags for {youtube_id}: {exc!s}"
            return ("error", msg)
        else:
            msg = f"Updated tags for YouTube video {youtube_id}"
            return ("success", msg)

    def print_summary(self, success_count, error_count, skipped_count):
        """Print summary of processing results"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Successfully updated: {success_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"Skipped: {skipped_count}"))
        total = success_count + error_count + skipped_count
        self.stdout.write(f"Total processed: {total}")

    def handle(self, *args, **options):  # noqa: C901, PLR0912, PLR0915
        """Execute the management command"""
        super().handle(*args, **options)

        verbosity = options.get("verbosity", 1)

        if not is_youtube_enabled():
            self.stdout.write(
                self.style.ERROR(
                    "YouTube integration is not enabled. Check YT_* settings."
                )
            )
            return

        dry_run = options["dry_run"]
        youtube_id_filter = options["youtube_id"]
        add_course_tag = options["add_course_tag"]

        if verbosity >= 1:
            self.stdout.write("Starting YouTube tag update...")

        if verbosity >= VERBOSITY_DETAILED:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "DRY RUN MODE - No changes will be made to YouTube"
                    )
                )

            if add_course_tag:
                self.stdout.write(
                    self.style.SUCCESS("Adding course name as tag for all videos")
                )

        video_resources = self.get_video_resources(youtube_id_filter)

        if not video_resources.exists():
            # Always show if no videos found
            self.stdout.write(
                self.style.WARNING("No video resources found matching criteria")
            )
            return

        if verbosity >= VERBOSITY_DETAILED:
            self.stdout.write(
                f"Found {video_resources.count()} video resources to process"
            )

        youtube = YouTubeApi()
        success_count = 0
        error_count = 0
        skipped_count = 0

        for video_resource in video_resources:
            status, message = self.process_video(
                video_resource, youtube, dry_run, add_course_tag, verbosity
            )

            if verbosity >= VERBOSITY_DETAILED:
                if status == "success":
                    self.stdout.write(self.style.SUCCESS(message))
                elif status == "error":
                    self.stdout.write(self.style.ERROR(message))
                else:  # skip
                    self.stdout.write(self.style.WARNING(message))
            elif status == "error":
                self.stdout.write(self.style.ERROR(message))

            if status == "success":
                success_count += 1
            elif status == "error":
                error_count += 1
            else:  # skip
                skipped_count += 1

        if verbosity >= 1:
            completion_msg = f"Completed: {success_count} updated"
            if error_count > 0:
                completion_msg += f", {error_count} errors"
            if skipped_count > 0:
                completion_msg += f", {skipped_count} skipped"

            if error_count > 0:
                self.stdout.write(self.style.WARNING(completion_msg))
            else:
                self.stdout.write(self.style.SUCCESS(completion_msg))

        if verbosity >= VERBOSITY_DETAILED:
            self.print_summary(success_count, error_count, skipped_count)
