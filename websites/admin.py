""" Websites Admin """
from django.contrib import admin
from django.db.models import JSONField
from guardian.admin import GuardedModelAdmin
from mitol.common.admin import TimestampedModelAdmin

from main.admin import PrettyJSONWidget
from websites.models import Website, WebsiteContent, WebsiteStarter


class WebsiteAdmin(TimestampedModelAdmin, GuardedModelAdmin):
    """Website Admin"""

    model = Website

    include_created_on_in_list = True
    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}
    search_fields = ("title", "name", "uuid")
    list_display = (
        "name",
        "title",
        "publish_date",
    )
    raw_id_fields = ("starter",)
    ordering = ("-created_on",)


class WebsiteContentAdmin(TimestampedModelAdmin):
    """WebsiteContent Admin"""

    model = WebsiteContent

    search_fields = (
        "title",
        "website__name",
        "website__uuid",
        "uuid",
        "parent__uuid",
    )
    list_display = ("uuid", "title", "type", "website", "parent")
    list_filter = ("type",)
    raw_id_fields = ("website", "parent")


class WebsiteStarterAdmin(TimestampedModelAdmin):
    """WebsiteStarter Admin"""

    model = WebsiteStarter

    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}
    include_created_on_in_list = True
    list_display = ("id", "name", "source", "commit")
    list_filter = ("source",)
    search_fields = ("name", "path")


admin.site.register(Website, WebsiteAdmin)
admin.site.register(WebsiteContent, WebsiteContentAdmin)
admin.site.register(WebsiteStarter, WebsiteStarterAdmin)
