"""Management command to update YouTube video tags without re-uploading videos"""

from django.conf import settings
from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from videos.utils import get_course_tag, parse_tags
from videos.youtube import YouTubeApi, is_youtube_enabled
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import WebsiteContent
from websites.utils import get_dict_field, set_dict_field

# Verbosity level for detailed output
VERBOSITY_DETAILED = 2


class Command(WebsiteFilterCommand):
    """Update YouTube video tags by merging YouTube and DB tags"""

    help = "Update YouTube video tags by merging current YouTube tags with DB tags"

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

    def flatten_tags(self, tags: list[str]) -> set[str]:
        """
        Flatten and normalize a list of tags, handling poorly formatted tags.
        Returns a set of cleaned, lowercase tags.

        Args:
            tags (list[str]): List of tags, some of which may contain commas
        Returns:
            set[str]: Set of cleaned, lowercase tags
        """

        tags_set = set()

        for tag in tags:
            if "," in tag:
                # Poorly formatted tag - split it
                tags_set.update(t.strip().lower() for t in tag.split(","))
            else:
                tags_set.add(tag.strip().lower())

        return {tag for tag in tags_set if tag}  # Remove empty tags

    def merge_tags(
        self,
        youtube_tags: list[str],
        db_tags: list[str],
        course_slug: str,
        *,
        add_course_tag: bool,
    ) -> tuple[str, bool]:
        """
        Merge tags from YouTube and database.

        Returns tuple: (merged_tags_str, tags_changed)

        """

        # Flatten and normalize YouTube tags
        youtube_tags_set = self.flatten_tags(youtube_tags)

        # Normalize DB tags
        db_tags_set = self.flatten_tags(db_tags)

        # Merge: YouTube tags and DB tags
        merged_tags = youtube_tags_set.union(db_tags_set)

        # Add course tag if requested and not already present
        if add_course_tag and course_slug and course_slug not in merged_tags:
            merged_tags.add(course_slug)

        # Sort alphabetically
        sorted_tags = sorted(merged_tags)

        return (
            ", ".join(sorted_tags) if sorted_tags else "",
            merged_tags != youtube_tags_set,
        )

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

        try:
            # Fetch current tags from YouTube
            video_response = (
                youtube.client.videos().list(part="snippet", id=youtube_id).execute()
            )

            if not video_response.get("items"):
                msg = f"Video {youtube_id} not found on YouTube"
                return ("error", msg)

            # Get current tags from YouTube
            youtube_tags = video_response["items"][0]["snippet"].get("tags", [])

            # Get tags from DB and parse to list
            db_tags_str = get_dict_field(
                video_resource.metadata, settings.YT_FIELD_TAGS
            )
            db_tags = parse_tags(db_tags_str or "")

            # Merge tags
            merged_tags, tags_changed = self.merge_tags(
                youtube_tags, db_tags, course_slug, add_course_tag=add_course_tag
            )

            # Display detailed info only at verbosity level 2+
            if verbosity >= VERBOSITY_DETAILED:
                self.stdout.write(
                    f"\nProcessing: {video_resource.title} ({website_name})"
                )
                self.stdout.write(f"  YouTube ID: {youtube_id}")
                self.stdout.write(
                    f"  Current YouTube tags: {', '.join(youtube_tags) or '(no tags)'}"
                )
                self.stdout.write(f"  Current DB tags: {db_tags_str or '(no tags)'}")
                self.stdout.write(f"  Merged tags: {merged_tags or '(no tags)'}")
                if add_course_tag and course_slug:
                    self.stdout.write(f"  Course tag: {course_slug}")
                if tags_changed:
                    self.stdout.write("  Tags will be updated")
                else:
                    self.stdout.write("  No tag changes needed")

            # Initialize status and message
            status = "skip"
            message = f"  No tag changes for {youtube_id}"

            if dry_run:
                # Dry run mode - don't update anything
                status = "success"
                message = f"  [DRY RUN] Would update tags to: {merged_tags}"
            else:
                if tags_changed:
                    # Update tags on YouTube
                    youtube.update_video_tags(youtube_id, merged_tags)
                    status = "success"
                    message = f"Updated tags for YouTube video {youtube_id}"

                # Always save merged tags to DB in normal mode
                set_dict_field(
                    video_resource.metadata, settings.YT_FIELD_TAGS, merged_tags
                )
                video_resource.save()

        except Exception as exc:  # noqa: BLE001
            status, message = "error", f"Error updating tags for {youtube_id}: {exc!s}"

        return status, message

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
