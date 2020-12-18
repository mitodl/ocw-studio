""" websites models """
from uuid import uuid4

from django.db import models

from main.models import TimestampedModel
from websites.constants import WEBSITE_TYPE_COURSE


class Website(TimestampedModel):
    """ Class for a generic website """

    uuid = models.UUIDField(primary_key=True, default=uuid4)
    url_path = models.CharField(unique=True, max_length=512, null=False, blank=False)
    title = models.CharField(max_length=512, null=True, blank=True)
    publish_date = models.DateTimeField(null=True, blank=True)
    type = models.CharField(
        max_length=24, default=WEBSITE_TYPE_COURSE, blank=False, null=False
    )
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        """Str representation for the Website"""
        return f"{self.url_path}"


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
        """Str representation for the Website"""
        return f"'{self.title}' ({self.uuid})'"
