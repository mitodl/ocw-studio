"""Tests for users.models"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from users.factories import UserFactory
from users.models import User, UserManager


pytestmark = pytest.mark.django_db


class TestUserManager:
    """Tests for UserManager"""

    def test_create_user(self):
        """Test creating a regular user"""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            name="Test User",
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.is_active is True
        assert user.check_password("testpass123")

    def test_create_user_without_name(self):
        """Test creating a user without a name"""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        assert user.name == ""

    def test_create_user_without_email(self):
        """Test creating a user without email"""
        user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        assert user.email == ""

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
        )
        assert user.username == "admin"
        assert user.email == "admin@example.com"
        assert user.name == "Admin User"
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True
        assert user.check_password("adminpass123")

    def test_create_superuser_invalid_is_staff(self):
        """Test creating a superuser with is_staff=False raises ValueError"""
        with pytest.raises(ValueError, match="Superuser must have is_staff=True."):
            User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="adminpass123",
                is_staff=False,
            )

    def test_create_superuser_invalid_is_superuser(self):
        """Test creating a superuser with is_superuser=False raises ValueError"""
        with pytest.raises(ValueError, match="Superuser must have is_superuser=True."):
            User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="adminpass123",
                is_superuser=False,
            )

    def test_normalize_email(self):
        """Test that email is normalized when creating a user"""
        user = User.objects.create_user(
            username="testuser", email="Test@EXAMPLE.COM", password="testpass123"
        )
        assert user.email == "Test@example.com"

    def test_unique_username_constraint(self):
        """Test that usernames must be unique"""
        User.objects.create_user(
            username="testuser", email="test1@example.com", password="testpass123"
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="testuser", email="test2@example.com", password="testpass123"
            )

    def test_unique_email_constraint(self):
        """Test that emails must be unique"""
        User.objects.create_user(
            username="testuser1", email="test@example.com", password="testpass123"
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="testuser2", email="test@example.com", password="testpass123"
            )


class TestUser:
    """Tests for User model"""

    def test_user_str_representation(self):
        """Test User string representation"""
        user = UserFactory.build(username="testuser", email="test@example.com")
        expected = "User username=testuser email=test@example.com"
        assert str(user) == expected

    def test_user_username_field(self):
        """Test that USERNAME_FIELD is set correctly"""
        assert User.USERNAME_FIELD == "username"

    def test_user_email_field(self):
        """Test that EMAIL_FIELD is set correctly"""
        assert User.EMAIL_FIELD == "email"

    def test_user_required_fields(self):
        """Test that REQUIRED_FIELDS are set correctly"""
        assert User.REQUIRED_FIELDS == ["email", "name"]

    def test_user_default_values(self):
        """Test default field values"""
        user = UserFactory.create()
        assert user.name == ""  # Default from factory
        assert user.is_staff is False
        assert user.is_active is True
        assert user.is_superuser is False

    def test_user_is_authenticated(self):
        """Test that user is authenticated (not anonymous)"""
        user = UserFactory.create()
        assert user.is_authenticated
        assert not user.is_anonymous

    def test_user_permissions(self):
        """Test user permissions functionality"""
        user = UserFactory.create()
        # Test basic permission methods exist and work
        assert hasattr(user, "has_perm")
        assert hasattr(user, "has_perms")
        assert hasattr(user, "has_module_perms")
        
        # Basic permission test (user has no permissions by default)
        assert not user.has_perm("some.permission")
        assert user.has_perms([])  # Empty list should return True

    def test_user_manager_assignment(self):
        """Test that the custom UserManager is properly assigned"""
        assert isinstance(User.objects, UserManager)

    def test_user_timestamped_model(self):
        """Test that User inherits from TimestampedModel"""
        user = UserFactory.create()
        assert hasattr(user, "created_on")
        assert hasattr(user, "updated_on")
        assert user.created_on is not None
        assert user.updated_on is not None

    def test_user_max_length_constraints(self):
        """Test field max_length constraints"""
        # Username max length is 255
        long_username = "a" * 256
        with pytest.raises(ValidationError):
            user = User(
                username=long_username,
                email="test@example.com"
            )
            user.full_clean()

    def test_user_blank_fields(self):
        """Test which fields can be blank"""
        user = User(
            username="testuser",
            email="test@example.com",
            name="",  # name can be blank
        )
        user.full_clean()  # Should not raise ValidationError

    def test_user_inactive_user(self):
        """Test inactive user behavior"""
        user = UserFactory.create(is_active=False)
        assert not user.is_active
        # Note: Authentication behavior with inactive users depends on backend configuration
