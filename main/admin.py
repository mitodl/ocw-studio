"""Django admin functionality that is relevant to the entire app"""

import json
import logging

import yaml
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import JSONField, widgets
from django.forms.utils import ErrorList

log = logging.getLogger(__name__)


class AuditableModelAdmin(admin.ModelAdmin):
    """A ModelAdmin which will save and log"""

    def save_model(self, request, obj, form, change):  # noqa: ARG002
        obj.save_and_log(request.user)


class SingletonModelAdmin(admin.ModelAdmin):
    """A ModelAdmin which enforces a singleton model"""

    def has_add_permission(self, request):  # noqa: ARG002
        """Overridden method - prevent adding an object if one already exists"""
        return self.model.objects.count() == 0


class TimestampedModelAdmin(admin.ModelAdmin):
    """
    A ModelAdmin that includes timestamp fields in the detail view and, optionally, in the list view
    """  # noqa: E501

    include_timestamps_in_list = False
    include_created_on_in_list = False

    @staticmethod
    def _join_and_dedupe(existing_field_names, field_names_to_add):
        """
        Joins two tuples of field names together, and ensures that no duplicate field names are added

        Args:
            existing_field_names (Tuple[str]): Field names
            field_names_to_add (Tuple[str]): Field names to add to the existing ones

        Returns:
            Tuple[str]: The combined field names without any duplicates, unless there were any duplicates in the
                tuple of existing field names
        """  # noqa: E501, D401
        return existing_field_names + tuple(
            field for field in field_names_to_add if field not in existing_field_names
        )

    def get_list_display(self, request):
        list_display = tuple(super().get_list_display(request) or ())
        added_fields = ()
        if self.include_timestamps_in_list:
            added_fields += ("created_on", "updated_on")
        elif self.include_created_on_in_list:
            added_fields += ("created_on",)
        return self._join_and_dedupe(list_display, added_fields)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = tuple(super().get_readonly_fields(request, obj=obj) or ())
        if obj is None:
            return readonly_fields
        return self._join_and_dedupe(readonly_fields, ("created_on", "updated_on"))

    def get_exclude(self, request, obj=None):
        exclude = tuple(super().get_exclude(request, obj=obj) or ())
        return self._join_and_dedupe(exclude, ("created_on", "updated_on"))


# Adapted from solution posted on StackOverflow: https://stackoverflow.com/a/52627264
class PrettyJSONWidget(widgets.Textarea):
    """Admin widget class to pretty-print JSONField contents"""

    def format_value(self, value):
        self.attrs["style"] = "font-family: monospace"
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value  # noqa: TRY300
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            log.warning("Error while formatting JSON: %s", e)
            return super().format_value(value)


class JsonOrYamlField(JSONField):
    """Custom form field that can accept JSON or YAML as an input value"""

    default_error_messages = {"invalid": "Enter valid JSON or YAML."}
    widget = PrettyJSONWidget

    def to_python(self, value):
        try:
            return super().to_python(value)
        except ValidationError as ex:
            # Try parsing as YAML
            try:
                return yaml.load(value, Loader=yaml.SafeLoader)
            except yaml.YAMLError:
                raise ex  # pylint: disable=raise-missing-from  # noqa: B904


class WhitespaceErrorList(ErrorList):
    """
    HACK: Custom Django admin error class that maintains the formatting of an error message
    if that message has line breaks/tabs/etc. Under normal circumstances, Django escapes HTML and ignores spacing
    characters for field error messages.

    If an error message has no line breaks, the message is returned in the normal format. If the error message does
    have line breaks, the message is returned in a custom format which maintains the whitespace defined in the
    error message string.
    """  # noqa: E501

    def as_ul(self):
        """Overrides base method. This is the method that is called to output an error for a single form field."""  # noqa: E501, D401
        if self.data:
            error_lines = self
            # If the error message has any line breaks, return a custom <ul> which maintains the spacing  # noqa: E501
            # in the message.
            if any("\n" in line for line in error_lines):
                error_lines = [
                    line.replace("\n", "<br />").replace("\t", "&nbsp;" * 4)
                    for line in error_lines
                ]
                error_list_items = "".join([f"<li>{line}</li>" for line in error_lines])
                return f'<ul class="{self.error_class}">{error_list_items}</ul>'
        return super().as_ul()
