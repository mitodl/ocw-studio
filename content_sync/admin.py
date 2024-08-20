"""Content sync admin"""

from django.contrib import admin
from mitol.common.admin import TimestampedModelAdmin

from content_sync.models import ContentSyncState


@admin.register(ContentSyncState)
class ContentSyncStateAdmin(TimestampedModelAdmin):
    """ContentSyncState Admin"""

    model = ContentSyncState

    include_created_on_in_list = True
    search_fields = (
        "content__text_id",
        "content__title",
        "content__website__name",
        "content__website__title",
    )
    list_display = (
        "get_content_title",
        "get_content_text_id",
        "get_website_name",
    )
    raw_id_fields = ("content",)
    ordering = ("-created_on",)

    def get_queryset(self, request):  # noqa: ARG002
        return self.model.objects.get_queryset().select_related("content__website")

    @admin.display(
        description="Content Title",
        ordering="content__title",
    )
    def get_content_title(self, obj):
        """Returns the related WebsiteContent title"""  # noqa: D401
        return obj.content.title

    @admin.display(
        description="Content Text ID",
        ordering="content__text_id",
    )
    def get_content_text_id(self, obj):
        """Returns the related WebsiteContent text ID"""  # noqa: D401
        return obj.content.text_id

    @admin.display(
        description="Website",
        ordering="content__website__name",
    )
    def get_website_name(self, obj):
        """Returns the related Website name"""  # noqa: D401
        return obj.content.website.name
