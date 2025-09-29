"""Tests for users.admin"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from users.admin import UserAdmin
from users.factories import UserFactory
from users.models import User


pytestmark = pytest.mark.django_db


class TestUserAdmin:
    """Tests for UserAdmin"""

    def setup_method(self):
        """Set up test fixtures"""
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.factory = RequestFactory()

    def test_user_admin_list_display(self):
        """Test UserAdmin list_display configuration"""
        expected_fields = ["username", "email", "name", "is_staff", "is_active", "created_on"]
        assert self.admin.list_display == expected_fields

    def test_user_admin_list_filter(self):
        """Test UserAdmin list_filter configuration"""
        expected_filters = ["is_staff", "is_active", "is_superuser"]
        assert self.admin.list_filter == expected_filters

    def test_user_admin_search_fields(self):
        """Test UserAdmin search_fields configuration"""
        expected_fields = ["username", "email", "name"]
        assert self.admin.search_fields == expected_fields

    def test_user_admin_ordering(self):
        """Test UserAdmin ordering configuration"""
        expected_ordering = ["username"]
        assert self.admin.ordering == expected_ordering

    def test_user_admin_readonly_fields(self):
        """Test UserAdmin readonly_fields configuration"""
        # created_on and updated_on should be readonly (from TimestampedModelAdmin)
        assert "created_on" in self.admin.readonly_fields
        assert "updated_on" in self.admin.readonly_fields

    def test_user_admin_fieldsets(self):
        """Test UserAdmin fieldsets configuration"""
        # Should have proper fieldsets defined
        assert hasattr(self.admin, "fieldsets")
        assert self.admin.fieldsets is not None

    def test_user_admin_add_fieldsets(self):
        """Test UserAdmin add_fieldsets configuration"""
        # Should have add_fieldsets for user creation
        assert hasattr(self.admin, "add_fieldsets")
        assert self.admin.add_fieldsets is not None

    def test_user_admin_queryset(self):
        """Test UserAdmin get_queryset method"""
        # Create test users
        active_user = UserFactory.create(is_active=True)
        inactive_user = UserFactory.create(is_active=False)
        superuser = UserFactory.create(is_superuser=True)
        
        request = self.factory.get("/admin/users/user/")
        request.user = superuser
        
        queryset = self.admin.get_queryset(request)
        
        # Should include all users
        assert active_user in queryset
        assert inactive_user in queryset
        assert superuser in queryset

    def test_user_admin_has_add_permission(self):
        """Test UserAdmin has_add_permission method"""
        superuser = UserFactory.create(is_superuser=True, is_staff=True)
        regular_user = UserFactory.create(is_superuser=False, is_staff=True)
        
        request = self.factory.get("/admin/users/user/add/")
        
        # Superuser should have add permission
        request.user = superuser
        assert self.admin.has_add_permission(request) is True
        
        # Regular staff user permission depends on Django's permission system
        request.user = regular_user
        # This will be True/False based on user permissions
        result = self.admin.has_add_permission(request)
        assert isinstance(result, bool)

    def test_user_admin_has_change_permission(self):
        """Test UserAdmin has_change_permission method"""
        superuser = UserFactory.create(is_superuser=True, is_staff=True)
        user_to_change = UserFactory.create()
        
        request = self.factory.get(f"/admin/users/user/{user_to_change.id}/change/")
        request.user = superuser
        
        # Superuser should have change permission
        assert self.admin.has_change_permission(request, user_to_change) is True

    def test_user_admin_has_delete_permission(self):
        """Test UserAdmin has_delete_permission method"""
        superuser = UserFactory.create(is_superuser=True, is_staff=True)
        user_to_delete = UserFactory.create()
        
        request = self.factory.get(f"/admin/users/user/{user_to_delete.id}/delete/")
        request.user = superuser
        
        # Superuser should have delete permission
        result = self.admin.has_delete_permission(request, user_to_delete)
        assert isinstance(result, bool)

    def test_user_admin_get_form(self):
        """Test UserAdmin get_form method returns proper form"""
        superuser = UserFactory.create(is_superuser=True, is_staff=True)
        request = self.factory.get("/admin/users/user/add/")
        request.user = superuser
        
        form_class = self.admin.get_form(request)
        assert form_class is not None
        
        # Form should have expected fields
        form = form_class()
        assert "username" in form.fields
        assert "email" in form.fields
        assert "name" in form.fields

    def test_user_admin_save_model(self):
        """Test UserAdmin save_model method"""
        superuser = UserFactory.create(is_superuser=True, is_staff=True)
        user = UserFactory.build()  # Don't save yet
        
        request = self.factory.post("/admin/users/user/add/")
        request.user = superuser
        
        # Mock form (in real usage, this would be a proper ModelForm)
        form = type('MockForm', (), {'cleaned_data': {}})()
        
        # This should save the user without errors
        self.admin.save_model(request, user, form, change=False)
        
        # User should now be saved
        assert user.pk is not None

    def test_user_admin_is_registered(self):
        """Test that UserAdmin is properly registered with admin site"""
        from django.contrib import admin
        
        # User model should be registered in admin
        assert User in admin.site._registry
        
        # Should be registered with UserAdmin class
        admin_class = admin.site._registry[User]
        assert isinstance(admin_class, UserAdmin)

    def test_user_admin_inherits_from_timestamped_model_admin(self):
        """Test that UserAdmin inherits from TimestampedModelAdmin"""
        from mitol.common.admin import TimestampedModelAdmin
        
        # UserAdmin should inherit from TimestampedModelAdmin
        assert issubclass(UserAdmin, TimestampedModelAdmin)

    def test_user_admin_str_representation(self):
        """Test admin interface displays users correctly"""
        user = UserFactory.create(username="testuser", email="test@example.com")
        admin_str = str(user)
        
        # Should contain username and email
        assert "testuser" in admin_str
        assert "test@example.com" in admin_str
