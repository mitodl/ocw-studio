""" websites models """
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
import yaml

from main.models import TimestampedModel
from websites.constants import WEBSITE_TYPE_COURSE, STARTER_SOURCES


def validate_yaml(value):
    """Validator function to ensure that the value is YAML-formatted"""
    try:
        yaml.load(value)
    except yaml.YAMLError as exc:
        raise ValidationError("Value must be YAML-formatted.") from exc


class Website(TimestampedModel):
    """ Class for a generic website """

    uuid = models.UUIDField(primary_key=True, default=uuid4)
    starter = models.ForeignKey(
        "WebsiteStarter", null=True, blank=True, on_delete=models.CASCADE
    )
    url_path = models.CharField(unique=True, max_length=512, null=False, blank=False)
    title = models.CharField(max_length=512, null=True, blank=True)
    publish_date = models.DateTimeField(null=True, blank=True)
    type = models.CharField(
        max_length=24, default=WEBSITE_TYPE_COURSE, blank=False, null=False
    )
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"'{self.title}' ({self.url_path})"


class WebsiteContent(TimestampedModel):
    """ Class for a content component of a website"""

    website = models.ForeignKey(
        "Website", null=False, blank=False, on_delete=models.CASCADE
    )
    uuid = models.UUIDField(null=False, blank=False, default=uuid4)
    title = models.CharField(max_length=512, null=True, blank=True)
    type = models.CharField(max_length=24, blank=True, null=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="contents", on_delete=models.CASCADE
    )
    markdown = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    hugo_filepath = models.CharField(max_length=2048, null=True, blank=True)

    class Meta:
        unique_together = [["website", "uuid"]]

    def __str__(self):
        return f"'{self.title}' ({self.uuid})'"


class WebsiteStarter(TimestampedModel):
    """ Represents a starter project that contains config/templates/etc. for the desired static site """

    path = models.CharField(
        max_length=256,
        null=False,
        help_text="Github repo path or local file path of the starter project.",
    )
    name = models.CharField(
        max_length=100,
        null=False,
        help_text="Human-friendly name of the starter project.",
    )
    source = models.CharField(
        max_length=15,
        null=False,
        choices=zip(STARTER_SOURCES, STARTER_SOURCES),
        db_index=True,
    )
    commit = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        help_text="Commit hash for the repo (if this commit came from a Github starter repo).",
    )
    config = models.TextField(
        null=False, help_text="YML-formatted site config.", validators=[validate_yaml]
    )

    def __str__(self):
        return f"name='{self.name}', source={self.source}, commit={self.commit}"
