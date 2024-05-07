"""Admin for videos"""

from django.contrib import admin
from mitol.common.admin import TimestampedModelAdmin

from videos.models import Video, VideoFile, VideoJob


class VideoFilesInline(admin.TabularInline):
    """Inline model for video files"""

    model = VideoFile
    extra = 0
    readonly_fields = ["s3_key"]


class VideoJobsInline(admin.TabularInline):
    """Inline model for video jobs"""

    model = VideoJob
    extra = 0

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        return False

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        return False


class VideoAdmin(TimestampedModelAdmin):
    """Video Admin"""

    model = Video

    include_created_on_in_list = True
    search_fields = (
        "source_key",
        "website__name",
        "website__title",
        "website__short_id",
    )
    autocomplete_fields = ["website"]
    inlines = [VideoFilesInline, VideoJobsInline]
    list_display = (
        "website",
        "source_key",
        "status",
    )
    list_filter = ("status",)
    ordering = ("-updated_on",)


admin.site.register(Video, VideoAdmin)
