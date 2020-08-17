"""Models for users"""
from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from main.models import TimestampedModel


class UserManager(BaseUserManager):
    """User manager for custom user model"""

    use_in_migrations = True

    @transaction.atomic
    def _create_user(self, username, email, password, **extra_fields):
        """Create and save a user with the given email and password"""
        email = self.normalize_email(email)
        fields = {**extra_fields, "email": email}
        if username is not None:
            fields["username"] = username

        user = self.model(**fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        """Create a user"""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        """Create a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, TimestampedModel, PermissionsMixin):
    """
    Custom User model
    """

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "name"]

    username = models.CharField(unique=True, max_length=255)
    email = models.EmailField(blank=False, unique=True)
    name = models.TextField(blank=True, default="")

    is_staff = models.BooleanField(
        default=False, help_text="The user can access the admin site"
    )
    is_active = models.BooleanField(
        default=False, help_text="The user account is active"
    )

    objects = UserManager()

    def __str__(self):
        """Str representation for the user"""
        return f"User username={self.username} email={self.email}"
