"""Admin for gdrive_sync"""

from django.contrib import admin
from mitol.common.admin import TimestampedModelAdmin

from gdrive_sync.models import DriveApiQueryTracker, DriveFile


@admin.register(DriveApiQueryTracker)
class DriveApiQueryTrackerAdmin(TimestampedModelAdmin):
    """DriveApiQueryTracker Admin"""

    model = DriveApiQueryTracker

    list_display = (
        "api_call",
        "last_dt",
    )


@admin.register(DriveFile)
class DriveFileAdmin(TimestampedModelAdmin):
    """DriveFile Admin"""

    model = DriveFile

    include_created_on_in_list = True
    search_fields = (
        "name",
        "website__name",
        "website__title",
        "website__short_id",
        "s3_key",
    )
    autocomplete_fields = ["website", "video", "resource"]
    list_display = (
        "name",
        "status",
    )
    list_filter = ("status", "mime_type")
    ordering = ("-modified_time",)
    readonly_fields = [
        "file_id",
        "drive_path",
        "modified_time",
        "size",
        "created_time",
        "download_link",
    ]
