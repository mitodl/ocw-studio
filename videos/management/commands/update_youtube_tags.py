"""Management command to update YouTube video tags without re-uploading videos"""

import csv
import logging
import math
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from googleapiclient.errors import HttpError

from main.management.commands.filter import WebsiteFilterCommand
from videos.tasks import update_youtube_tags_batch
from videos.utils import get_course_tag, parse_tags
from videos.youtube import API_QUOTA_ERROR_MSG, YouTubeApi, is_youtube_enabled
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import WebsiteContent
from websites.utils import get_dict_field, set_dict_field

log = logging.getLogger(__name__)

# Verbosity level for detailed output
VERBOSITY_DETAILED = 2

# YouTube Data API v3 quota costs
QUOTA_COST_VIDEO_LIST = 1  # videos.list costs 1 unit
QUOTA_COST_VIDEO_UPDATE = 50  # videos.update costs 50 units

# Maximum video IDs per videos.list call
YT_LIST_BATCH_SIZE = 50

# Default daily quota limit (conservative to leave room for other usage)
DEFAULT_QUOTA_LIMIT = 9000


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
            help=(
                "Update videos with specific YouTube ID(s). Supports "
                "comma-separated list (e.g., 'id1,id2,id3')"
            ),
        )
        parser.add_argument(
            "--add-course-tag",
            action="store_true",
            default=False,
            help="Automatically add course name (URL slug) as a tag",
        )
        parser.add_argument(
            "--out",
            dest="output_file",
            default=None,
            help=(
                "Export results to CSV file with columns: vid_resource_id, "
                "existing_yt_tags, existing_db_tags, final_tags_yt, "
                "final_tags_db"
            ),
        )
        parser.add_argument(
            "--batch-size",
            dest="batch_size",
            type=int,
            default=None,
            help=(
                "Maximum number of videos to process in this run. "
                "Use with --offset to process in batches across multiple runs."
            ),
        )
        parser.add_argument(
            "--offset",
            dest="offset",
            type=int,
            default=0,
            help=(
                "Number of videos to skip from the beginning of the queryset. "
                "Use with --batch-size to resume from where you left off."
            ),
        )
        parser.add_argument(
            "--quota-limit",
            dest="quota_limit",
            type=int,
            default=DEFAULT_QUOTA_LIMIT,
            help=(
                f"Stop processing before exceeding this quota unit limit "
                f"(default: {DEFAULT_QUOTA_LIMIT}). YouTube Data API v3 "
                f"default daily quota is 10,000 units. "
                f"videos.list = {QUOTA_COST_VIDEO_LIST} unit, "
                f"videos.update = {QUOTA_COST_VIDEO_UPDATE} units."
            ),
        )
        parser.add_argument(
            "--schedule",
            action="store_true",
            default=False,
            help=(
                "When the number of videos exceeds the batch threshold "
                f"(YT_BATCH_THRESHOLD, default {settings.YT_BATCH_THRESHOLD}), "
                "automatically schedule Celery tasks spread across multiple "
                "days instead of updating immediately. If the count is below "
                "the threshold, updates run immediately regardless."
            ),
        )

    def get_video_resources(self, youtube_id_filter, *, offset=0, batch_size=None):
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
            # Handle comma-separated YouTube IDs
            youtube_ids = [
                yt_id.strip() for yt_id in youtube_id_filter.split(",") if yt_id.strip()
            ]
            if youtube_ids:
                video_resources = video_resources.filter(
                    **{f"{query_id_field}__in": youtube_ids}
                )

        # Apply stable ordering for consistent offset/batch behavior
        video_resources = video_resources.order_by("id")

        # Apply offset and batch_size
        if batch_size is not None:
            video_resources = video_resources[offset : offset + batch_size]
        elif offset > 0:
            video_resources = video_resources[offset:]

        return video_resources

    def batch_fetch_youtube_snippets(self, youtube, youtube_ids):
        """
        Fetch video snippets from YouTube in batches of up to 50 IDs per call.

        The YouTube videos.list API accepts comma-separated IDs and costs
        1 quota unit regardless of how many IDs are included (up to 50).

        Args:
            youtube: YouTubeApi instance
            youtube_ids: List of YouTube video IDs

        Returns:
            tuple: (dict mapping youtube_id -> snippet, quota_used)
        """
        snippets = {}
        quota_used = 0

        for i in range(0, len(youtube_ids), YT_LIST_BATCH_SIZE):
            batch = youtube_ids[i : i + YT_LIST_BATCH_SIZE]
            batch_ids = ",".join(batch)

            response = (
                youtube.client.videos().list(part="snippet", id=batch_ids).execute()
            )
            quota_used += QUOTA_COST_VIDEO_LIST

            for item in response.get("items", []):
                video_id = item["id"]
                snippets[video_id] = item["snippet"]

        return snippets, quota_used

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
        self,
        video_resource,
        youtube,
        dry_run,
        add_course_tag,
        verbosity,
        snippet=None,
    ):
        """
        Process a single video resource to update its tags.

        Args:
            video_resource: WebsiteContent object
            youtube: YouTubeApi instance
            dry_run: Preview changes without updating
            add_course_tag: Add course slug as tag
            verbosity: Output verbosity level
            snippet: Pre-fetched YouTube snippet dict (avoids redundant API call)

        Returns tuple: (status, message, csv_data, quota_used) where:
        - status is 'success', 'error', or 'skip'
        - message is a string describing the result
        - csv_data is a dict with CSV export data (or None on error)
        - quota_used is the number of quota units consumed
        """
        youtube_id = get_dict_field(video_resource.metadata, settings.YT_FIELD_ID)
        course_slug = get_course_tag(video_resource.website)
        website_name = video_resource.website.name
        quota_used = 0

        try:
            if snippet is None:
                # Fallback: fetch from YouTube if not pre-fetched
                video_response = (
                    youtube.client.videos()
                    .list(part="snippet", id=youtube_id)
                    .execute()
                )
                quota_used += QUOTA_COST_VIDEO_LIST

                if not video_response.get("items"):
                    msg = f"Video {youtube_id} not found on YouTube"
                    return ("error", msg, None, quota_used)

                snippet = video_response["items"][0]["snippet"]
            elif snippet == "not_found":
                msg = f"Video {youtube_id} not found on YouTube"
                return ("error", msg, None, quota_used)

            # Get current tags from YouTube
            youtube_tags = snippet.get("tags", [])

            # Get tags from DB and parse to list
            db_tags_str = get_dict_field(
                video_resource.metadata, settings.YT_FIELD_TAGS
            )
            db_tags = parse_tags(db_tags_str or "")

            # Store initial tags for CSV export
            initial_yt_tags = ", ".join(youtube_tags)
            initial_db_tags = db_tags_str or ""

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
                    # Update tags directly using the already-fetched snippet
                    # This avoids the redundant videos.list call in
                    # update_video_tags
                    snippet["tags"] = parse_tags(merged_tags)
                    youtube.client.videos().update(
                        part="snippet",
                        body={
                            "id": youtube_id,
                            "snippet": snippet,
                        },
                    ).execute()
                    quota_used += QUOTA_COST_VIDEO_UPDATE

                    status = "success"
                    message = f"Updated tags for YouTube video {youtube_id}"

                # Always save merged tags to DB in normal mode
                set_dict_field(
                    video_resource.metadata, settings.YT_FIELD_TAGS, merged_tags
                )
                video_resource.save()

            # Prepare CSV data
            csv_data = {
                "vid_resource_id": video_resource.id,
                "existing_yt_tags": initial_yt_tags,
                "existing_db_tags": initial_db_tags,
                "final_tags": merged_tags,
                "youtube_updated": tags_changed and not dry_run,
                "db_updated": not dry_run,
            }

        except HttpError as exc:
            if API_QUOTA_ERROR_MSG in str(exc).lower():
                raise
            status, message = "error", f"Error updating tags for {youtube_id}: {exc!s}"
            csv_data = None
        except Exception as exc:  # noqa: BLE001
            status, message = "error", f"Error updating tags for {youtube_id}: {exc!s}"
            csv_data = None

        return status, message, csv_data, quota_used

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

    @staticmethod
    def _seconds_until_next_saturday():
        """Return seconds from now until the start of the next Saturday (UTC)."""
        now = timezone.now()
        days_ahead = (5 - now.weekday()) % 7  # Saturday = 5
        if days_ahead == 0 and now.hour >= 12:  # noqa: PLR2004
            # Already Saturday afternoon — push to next Saturday
            days_ahead = 7
        next_saturday = now.replace(
            hour=6, minute=0, second=0, microsecond=0
        ) + timedelta(days=days_ahead)
        return max(0, int((next_saturday - now).total_seconds()))

    def _schedule_celery_tasks(self, video_resources, add_course_tag, verbosity):
        """
        Schedule Celery tasks to process videos spread across multiple days.

        Calculates how many videos can be updated per day based on the daily
        quota, then creates tasks with increasing countdown delays (24h apart).

        If YT_SCHEDULE_WEEKENDS_ONLY is True, tasks are delayed so they only
        run on Saturdays and Sundays (2 slots per week).
        """
        daily_quota = settings.YT_DAILY_QUOTA
        weekends_only = settings.YT_SCHEDULE_WEEKENDS_ONLY
        # Each video that needs updating costs up to 50 units (videos.update)
        # plus a small overhead for batch list calls (~1 unit per 50 videos)
        # Conservative estimate: assume all videos need updating
        videos_per_day = max(
            1,
            (daily_quota - 10) // QUOTA_COST_VIDEO_UPDATE,  # reserve 10 for list calls
        )

        # Collect all YouTube IDs
        all_youtube_ids = []
        for vr in video_resources:
            yt_id = get_dict_field(vr.metadata, settings.YT_FIELD_ID)
            if yt_id and yt_id not in all_youtube_ids:
                all_youtube_ids.append(yt_id)

        total_videos = len(all_youtube_ids)
        total_chunks = math.ceil(total_videos / videos_per_day)
        seconds_per_day = 24 * 60 * 60

        # Build countdown schedule
        if weekends_only:
            # Schedule on Saturdays and Sundays only
            base_delay = self._seconds_until_next_saturday()
            countdowns = []
            for chunk_idx in range(total_chunks):
                # 0 -> Saturday, 1 -> Sunday, 2 -> next Saturday, 3 -> next Sunday...
                week_offset = chunk_idx // 2
                is_sunday = chunk_idx % 2 == 1
                delay = base_delay + (week_offset * 7 * seconds_per_day)
                if is_sunday:
                    delay += seconds_per_day
                countdowns.append(delay)
            num_weekends = math.ceil(total_chunks / 2)
            schedule_desc = f"{num_weekends} weekend(s) (Sat/Sun only)"
        else:
            countdowns = [
                (i // videos_per_day) * seconds_per_day
                for i in range(0, total_videos, videos_per_day)
            ]
            num_days = len(countdowns)
            schedule_desc = f"{num_days} day(s)"

        self.stdout.write(
            self.style.WARNING(
                f"\n{total_videos} videos exceed the batch threshold "
                f"({settings.YT_BATCH_THRESHOLD}). Scheduling Celery tasks "
                f"spread across {schedule_desc}."
            )
        )
        self.stdout.write(
            f"  Videos per day: ~{videos_per_day} "
            f"(based on {daily_quota} daily quota units)"
        )
        if weekends_only:
            self.stdout.write(
                "  Weekend-only mode: tasks will run on Saturdays and Sundays"
            )

        tasks_scheduled = 0
        for chunk_idx, countdown in enumerate(countdowns):
            start = chunk_idx * videos_per_day
            chunk = all_youtube_ids[start : start + videos_per_day]
            if not chunk:
                break

            update_youtube_tags_batch.apply_async(
                args=[chunk],
                kwargs={"add_course_tag": add_course_tag},
                countdown=countdown,
            )
            tasks_scheduled += 1

            if verbosity >= VERBOSITY_DETAILED:
                if countdown == 0:
                    self.stdout.write(
                        f"  Task {tasks_scheduled}: {len(chunk)} videos "
                        f"(running immediately)"
                    )
                else:
                    hours = countdown // 3600
                    self.stdout.write(
                        f"  Task {tasks_scheduled}: {len(chunk)} videos "
                        f"(scheduled in ~{hours}h)"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduled {tasks_scheduled} Celery task(s) for "
                f"{total_videos} videos across {schedule_desc}."
            )
        )

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
        output_file = options["output_file"]
        batch_size = options["batch_size"]
        offset = options["offset"]
        quota_limit = options["quota_limit"]
        schedule = options["schedule"]

        # Initialize CSV data collection if output file specified
        csv_rows = [] if output_file else None

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

        video_resources = self.get_video_resources(
            youtube_id_filter, offset=offset, batch_size=batch_size
        )

        # Convert to list to allow len() and iteration on sliced querysets
        video_resources = list(video_resources)

        if not video_resources:
            # Always show if no videos found
            self.stdout.write(
                self.style.WARNING("No video resources found matching criteria")
            )
            return

        video_count = len(video_resources)
        threshold = settings.YT_BATCH_THRESHOLD

        if verbosity >= VERBOSITY_DETAILED:
            self.stdout.write(f"Found {video_count} video resources to process")
            if offset > 0:
                self.stdout.write(f"  Offset: {offset}")
            if batch_size:
                self.stdout.write(f"  Batch size: {batch_size}")
            self.stdout.write(f"  Quota limit: {quota_limit} units")

        # If --schedule is set and count exceeds threshold, dispatch to Celery
        if schedule and video_count > threshold and not dry_run:
            self._schedule_celery_tasks(video_resources, add_course_tag, verbosity)
            return

        youtube = YouTubeApi()
        success_count = 0
        error_count = 0
        skipped_count = 0
        total_quota_used = 0
        quota_exceeded = False

        # Collect all YouTube IDs for batch fetching
        yt_id_to_resources = {}
        for vr in video_resources:
            yt_id = get_dict_field(vr.metadata, settings.YT_FIELD_ID)
            if yt_id:
                yt_id_to_resources.setdefault(yt_id, []).append(vr)

        all_youtube_ids = list(yt_id_to_resources.keys())

        if verbosity >= VERBOSITY_DETAILED:
            self.stdout.write(
                f"Batch-fetching snippets for {len(all_youtube_ids)} YouTube IDs "
                f"in {(len(all_youtube_ids) + YT_LIST_BATCH_SIZE - 1) // YT_LIST_BATCH_SIZE} API call(s)..."
            )

        # Batch-fetch all YouTube snippets
        try:
            snippets, list_quota = self.batch_fetch_youtube_snippets(
                youtube, all_youtube_ids
            )
            total_quota_used += list_quota
        except HttpError as exc:
            if API_QUOTA_ERROR_MSG in str(exc).lower():
                self.stdout.write(
                    self.style.ERROR(
                        f"YouTube API quota exceeded during batch fetch. "
                        f"Quota used so far: {total_quota_used} units. "
                        f"Try again tomorrow or use --batch-size and --offset."
                    )
                )
                return
            raise
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(
                self.style.ERROR(f"Error fetching video data from YouTube: {exc!s}")
            )
            return

        if verbosity >= VERBOSITY_DETAILED:
            self.stdout.write(
                f"Fetched {len(snippets)} snippets "
                f"({total_quota_used} quota units used for list calls)"
            )

        for video_resource in video_resources:
            yt_id = get_dict_field(video_resource.metadata, settings.YT_FIELD_ID)

            # Check if we have enough quota for a potential update
            if not dry_run and (
                total_quota_used + QUOTA_COST_VIDEO_UPDATE > quota_limit
            ):
                quota_exceeded = True
                remaining = len(video_resources) - (
                    success_count + error_count + skipped_count
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"\nQuota limit reached ({total_quota_used}/{quota_limit} units used). "
                        f"{remaining} videos remaining. "
                        f"Re-run with --offset {offset + success_count + error_count + skipped_count} "
                        f"to continue."
                    )
                )
                break

            # Look up pre-fetched snippet (or mark as not found)
            snippet = snippets.get(yt_id, "not_found") if yt_id else None

            status, message, csv_data, video_quota = self.process_video(
                video_resource,
                youtube,
                dry_run,
                add_course_tag,
                verbosity,
                snippet=snippet,
            )
            total_quota_used += video_quota

            # Collect CSV data if output file specified
            if csv_rows is not None and csv_data:
                csv_rows.append(csv_data)

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
            completion_msg += f" ({total_quota_used} quota units used)"

            if quota_exceeded or error_count > 0:
                self.stdout.write(self.style.WARNING(completion_msg))
            else:
                self.stdout.write(self.style.SUCCESS(completion_msg))

        if verbosity >= VERBOSITY_DETAILED:
            self.print_summary(success_count, error_count, skipped_count)

        # Write CSV file if specified
        if output_file and csv_rows:
            try:
                output_path = Path(output_file)
                with output_path.open("w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = [
                        "vid_resource_id",
                        "existing_yt_tags",
                        "existing_db_tags",
                        "final_tags",
                        "youtube_updated",
                        "db_updated",
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(csv_rows)

                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Exported {len(csv_rows)} records to {output_file}"
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"Error writing CSV file: {exc!s}"))
