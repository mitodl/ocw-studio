""" websites models """
import json
from hashlib import sha256
from uuid import uuid4

import yaml
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import SET_NULL, Q, UniqueConstraint
from django.utils.text import slugify
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet
from safedelete.managers import (
    SafeDeleteAllManager,
    SafeDeleteDeletedManager,
    SafeDeleteManager,
)
from safedelete.models import SafeDeleteModel
from safedelete.queryset import SafeDeleteQueryset

from main.utils import uuid_string
from users.models import User
from websites import constants
from websites.constants import (
    CONTENT_DIRPATH_MAX_LEN,
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_FILEPATH_UNIQUE_CONSTRAINT,
)
from websites.utils import permissions_group_name_for_role


def validate_yaml(value):
    """Validator function to ensure that the value is YAML-formatted"""
    try:
        yaml.load(value, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        raise ValidationError("Value must be YAML-formatted.") from exc


def validate_slug(value):
    """Validator function to ensure that the value is a properly-formatted slug"""
    slugified = slugify(value)
    if slugified != value:
        raise ValidationError(
            f"Value '{value}' is not a proper slug (slugified version: {slugified})"
        )


class Website(TimestampedModel):
    """ Class for a generic website """

    owner = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    uuid = models.UUIDField(primary_key=True, default=uuid4)
    starter = models.ForeignKey(
        "WebsiteStarter", null=True, blank=True, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=512, db_index=True, unique=True)
    title = models.CharField(max_length=512, null=False)
    source = models.CharField(
        max_length=20,
        choices=zip(constants.WEBSITE_SOURCES, constants.WEBSITE_SOURCES),
        default=constants.WEBSITE_SOURCE_STUDIO,
        null=True,
        blank=True,
    )
    publish_date = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    @property
    def admin_group(self):
        """ Get the admin group """
        return Group.objects.filter(
            name=permissions_group_name_for_role(constants.ROLE_ADMINISTRATOR, self)
        ).first()

    @property
    def editor_group(self):
        """ Get the editor group """
        return Group.objects.filter(
            name=permissions_group_name_for_role(constants.ROLE_EDITOR, self)
        ).first()

    class Meta:
        permissions = (
            ("publish_website", "Publish or unpublish a website"),
            ("preview_website", "Create preview markdowm"),
            (
                "add_collaborators_website",
                "Add or remove collaborators (admins, editors, etc)",
            ),
            ("edit_content_website", "Edit website content"),
        )

    def __str__(self):
        return f"'{self.title}' ({self.name})"


class WebsiteContentQuerySet(TimestampedModelQuerySet, SafeDeleteQueryset):
    """ Queryset for WebsiteContent """


class WebsiteContent(TimestampedModel, SafeDeleteModel):
    """ Class for a content component of a website"""

    objects = SafeDeleteManager(WebsiteContentQuerySet)
    all_objects = SafeDeleteAllManager(WebsiteContentQuerySet)
    deleted_objects = SafeDeleteDeletedManager(WebsiteContentQuerySet)

    def upload_file_to(self, filename):
        """Return the appropriate filepath for an upload"""
        return f"{self.website.name}/{self.text_id.replace('-', '')}_{filename}"

    owner = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=SET_NULL, related_name="content_updated"
    )
    website = models.ForeignKey(
        "Website", null=False, blank=False, on_delete=models.CASCADE
    )
    text_id = models.CharField(
        max_length=36, null=False, blank=False, default=uuid_string, db_index=True
    )
    title = models.CharField(max_length=512, null=True, blank=True)
    type = models.CharField(max_length=24, blank=False, null=False)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="contents", on_delete=models.CASCADE
    )
    markdown = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    is_page_content = models.BooleanField(
        default=False,
        help_text=(
            "If True, indicates that this content represents a navigable page, as opposed to some "
            "metadata, configuration, etc."
        ),
    )
    filename = models.CharField(
        max_length=CONTENT_FILENAME_MAX_LEN,
        null=False,
        default="",
        help_text="The filename of the file that will be created from this object WITHOUT the file extension.",
    )
    dirpath = models.CharField(
        max_length=CONTENT_DIRPATH_MAX_LEN,
        null=False,
        default="",
        help_text=(
            "The directory path for the file that will be created from this object."
        ),
    )
    file = models.FileField(
        upload_to=upload_file_to, editable=True, null=True, blank=True, max_length=2048
    )

    @staticmethod
    def generate_filename(title: str) -> str:
        """Generates a filename from a title value"""
        return slugify(title)[0:CONTENT_FILENAME_MAX_LEN]

    def calculate_checksum(self) -> str:
        """ Returns a calculated checksum of the content """
        return sha256(
            "\n".join(
                [
                    json.dumps(self.metadata, sort_keys=True),
                    str(self.title),
                    str(self.markdown),
                    self.type,
                    str(self.dirpath),
                    str(self.filename),
                ]
            ).encode("utf-8")
        ).hexdigest()

    class Meta:
        constraints = [
            UniqueConstraint(name="unique_text_id", fields=["website", "text_id"]),
            UniqueConstraint(
                name=CONTENT_FILEPATH_UNIQUE_CONSTRAINT,
                fields=("website", "dirpath", "filename"),
                condition=Q(is_page_content=True),
            ),
        ]

    def __str__(self):
        return f"{self.title} [{self.text_id}]" if self.title else str(self.text_id)


class WebsiteStarter(TimestampedModel):
    """ Represents a starter project that contains config/templates/etc. for the desired static site """

    path = models.CharField(
        max_length=256,
        null=False,
        help_text="Github repo path or local file path of the starter project.",
    )
    slug = models.CharField(
        max_length=30,
        null=False,
        unique=True,
        help_text="Short string that can be used to identify this starter.",
        validators=[validate_slug],
    )
    name = models.CharField(
        max_length=100,
        null=False,
        help_text="Human-friendly name of the starter project.",
    )
    source = models.CharField(
        max_length=15,
        null=False,
        choices=zip(constants.STARTER_SOURCES, constants.STARTER_SOURCES),
        db_index=True,
    )
    commit = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        help_text="Commit hash for the repo (if this commit came from a Github starter repo).",
    )
    config = models.JSONField(
        null=False, help_text="Site config describing content types, widgets, etc."
    )

    def __str__(self):
        return f"name='{self.name}', source={self.source}, commit={self.commit}"


class WebsiteCollection(TimestampedModel):
    """An ordered list of websites"""

    title = models.CharField(
        max_length=200, null=False, help_text="A title for the WebsiteCollection"
    )
    description = models.TextField(
        null=True, blank=True, help_text="A description for the WebsiteCollection"
    )

    def __str__(self):
        return f"WebsiteCollection '{self.title}'"


class WebsiteCollectionItem(TimestampedModel):
    """An entry in a WebsiteCollection"""

    website_collection = models.ForeignKey(
        WebsiteCollection, null=False, blank=False, on_delete=models.CASCADE
    )
    website = models.ForeignKey(
        Website, null=False, blank=False, on_delete=models.CASCADE
    )
    position = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.website_collection.title}[{self.position}]: {self.website.title}"
