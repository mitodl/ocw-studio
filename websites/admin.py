""" Websites Admin """
from django.contrib import admin
from main.admin import TimestampedModelAdmin
from websites.models import Website, WebsiteContent


class WebsiteAdmin(TimestampedModelAdmin):
    """Website Admin"""

    model = Website

    search_fields = ("title", "url_path", "uuid")
    list_display = (
        "url_path",
        "title",
        "publish_date",
        "type",
    )
    list_filter = ("type",)


class WebsiteContentAdmin(TimestampedModelAdmin):
    """WebsiteContent Admin"""

    model = WebsiteContent

    search_fields = (
        "title",
        "website__url_path",
        "website__uuid",
        "uuid",
        "parent__uuid",
    )
    list_display = ("uuid", "title", "type", "website", "parent")
    list_filter = ("type",)
    autocomplete_fields = ("website", "parent")


admin.site.register(Website, WebsiteAdmin)
admin.site.register(WebsiteContent, WebsiteContentAdmin)
