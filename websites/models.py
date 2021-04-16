""" websites models """
import json
from hashlib import sha256
from uuid import uuid4

import yaml
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import SET_NULL
from django.utils.text import slugify
from mitol.common.models import TimestampedModel

from users.models import User
from websites import constants
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


class WebsiteContent(TimestampedModel):
    """ Class for a content component of a website"""

    def upload_file_to(self, filename):
        """Return the appropriate filepath for an upload"""
        return f"{self.website.name}/{self.uuid.hex}_{filename}"

    owner = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    website = models.ForeignKey(
        "Website", null=False, blank=False, on_delete=models.CASCADE
    )
    uuid = models.UUIDField(null=False, blank=False, default=uuid4)
    title = models.CharField(max_length=512, null=True, blank=True)
    type = models.CharField(max_length=24, blank=False, null=False)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="contents", on_delete=models.CASCADE
    )
    markdown = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    content_filepath = models.CharField(max_length=2048, null=True, blank=True)
    file = models.FileField(
        upload_to=upload_file_to, editable=True, null=True, blank=True, max_length=2048
    )

    def calculate_checksum(self) -> str:
        """ Returns a calculated checksum of the content """
        return sha256(
            "\n".join([json.dumps(self.metadata), str(self.markdown)]).encode("utf-8")
        ).hexdigest()

    class Meta:
        unique_together = [["website", "uuid"]]

    def __str__(self):
        return f"{self.title} ({self.uuid})" if self.title else str(self.uuid)


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
