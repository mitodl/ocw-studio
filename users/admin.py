"""User admin"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as ContribUserAdmin
from django.utils.translation import gettext_lazy as _

from main.admin import TimestampedModelAdmin
from users.models import User


class UserAdmin(ContribUserAdmin, TimestampedModelAdmin):
    """Admin views for user"""

    include_created_on_in_list = True
    fieldsets = (
        (None, {"fields": ("username", "password", "last_login", "created_on")}),
        (_("Personal Info"), {"fields": ("name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ["collapse"],
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "name",
        "is_staff",
        "last_login",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "name", "email")
    ordering = ("email",)
    readonly_fields = ("username", "last_login")


admin.site.register(User, UserAdmin)
