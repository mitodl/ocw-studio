""" Websites Admin """
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.fields import JSONField
from guardian.admin import GuardedModelAdmin
from mitol.common.admin import TimestampedModelAdmin
from safedelete.admin import SafeDeleteAdmin, highlight_deleted

from main.admin import JsonOrYamlField, PrettyJSONWidget, WhitespaceErrorList
from websites.config_schema.api import validate_parsed_site_config
from websites.models import Website, WebsiteContent, WebsiteStarter


class WebsiteAdmin(TimestampedModelAdmin, GuardedModelAdmin):
    """Website Admin"""

    model = Website

    include_created_on_in_list = True
    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}
    search_fields = ("title", "name", "uuid", "short_id")
    readonly_fields = ("unpublish_status",)
    list_display = (
        "name",
        "title",
        "publish_date",
        "first_published_to_production",
        "unpublished",
    )
    list_filter = (
        ("unpublish_status", admin.EmptyFieldListFilter),
        ("first_published_to_production", admin.EmptyFieldListFilter),
        "starter__name",
    )
    raw_id_fields = ("starter",)
    ordering = ("-created_on",)


class WebsiteContentAdmin(TimestampedModelAdmin, SafeDeleteAdmin):
    """WebsiteContent Admin"""

    model = WebsiteContent

    include_created_on_in_list = True
    search_fields = (
        "title",
        "website__title",
        "website__name",
        "website__uuid",
        "website__short_id",
        "text_id",
        "parent__text_id",
    )
    list_display = (
        highlight_deleted,
        "text_id",
        "title",
        "type",
        "get_website_title",
    ) + SafeDeleteAdmin.list_display
    list_filter = ("type",) + SafeDeleteAdmin.list_filter
    raw_id_fields = ("website", "parent")
    ordering = ("-created_on",)

    def get_queryset(self, request):
        return self.model.objects.get_queryset().select_related("website", "parent")

    def get_website_title(self, obj):
        """Returns the related Website title"""
        return obj.website.title

    get_website_title.short_description = "Website"
    get_website_title.admin_order_field = "website__title"


class WebsiteStarterForm(forms.ModelForm):
    """Custom form for the WebsiteStarter model"""

    class Meta:
        model = WebsiteStarter
        field_classes = {
            "config": JsonOrYamlField,
        }
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        kwargs_updated = {**kwargs, "error_class": WhitespaceErrorList}
        super().__init__(*args, **kwargs_updated)

    def clean_config(self):
        """Ensures that the site config value obeys our schema"""
        config = self.cleaned_data["config"]
        try:
            validate_parsed_site_config(config)
        except ValueError as ex:
            raise ValidationError(str(ex)) from ex
        return config


class WebsiteStarterAdmin(TimestampedModelAdmin):
    """WebsiteStarter Admin"""

    model = WebsiteStarter

    form = WebsiteStarterForm
    include_created_on_in_list = True
    list_display = ("id", "name", "source", "commit")
    list_filter = ("source",)
    search_fields = ("name", "path")


admin.site.register(Website, WebsiteAdmin)
admin.site.register(WebsiteContent, WebsiteContentAdmin)
admin.site.register(WebsiteStarter, WebsiteStarterAdmin)
