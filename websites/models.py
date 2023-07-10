""" websites models """
import json
import logging
import re
from hashlib import sha256
from typing import Dict, Iterator, Tuple
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import yaml
from bulk_update_or_create import BulkUpdateOrCreateQuerySet
from django.conf import settings
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

from content_sync.constants import VERSION_LIVE
from main.settings import YT_FIELD_CAPTIONS, YT_FIELD_TRANSCRIPT
from main.utils import uuid_string
from users.models import User
from websites import constants
from websites.constants import (
    CONTENT_DIRPATH_MAX_LEN,
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_FILEPATH_UNIQUE_CONSTRAINT,
    CONTENT_TYPE_METADATA,
    WEBSITE_STARTER_STATUS_CHOICES,
    WebsiteStarterStatus,
)
from websites.site_config_api import ConfigItem, SiteConfig
from websites.utils import (
    get_dict_field,
    permissions_group_name_for_role,
    set_dict_field,
)


log = logging.getLogger(__name__)


def validate_yaml(value):
    """Validator function to ensure that the value is YAML-formatted"""
    try:
        yaml.load(value, Loader=yaml.SafeLoader)
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
    """Class for a generic website"""

    owner = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    uuid = models.UUIDField(primary_key=True, default=uuid4)
    starter = models.ForeignKey(
        "WebsiteStarter", null=True, blank=True, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=512, db_index=True, unique=True)
    short_id = models.CharField(max_length=100, db_index=True, unique=True, null=False)
    title = models.CharField(max_length=512, null=False, db_index=True)
    source = models.CharField(
        max_length=20,
        choices=zip(constants.WEBSITE_SOURCES, constants.WEBSITE_SOURCES),
        default=constants.WEBSITE_SOURCE_STUDIO,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(null=True, blank=True)

    first_published_to_production = models.DateTimeField(null=True, blank=True)

    # Live publish fields
    publish_date = models.DateTimeField(null=True, blank=True)
    has_unpublished_live = models.BooleanField(default=True)
    latest_build_id_live = models.IntegerField(null=True, blank=True)
    live_publish_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=zip(constants.PUBLISH_STATUSES, constants.PUBLISH_STATUSES),
    )
    live_last_published_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="live_publisher",
    )

    # Draft publish fields
    draft_publish_date = models.DateTimeField(null=True, blank=True)
    has_unpublished_draft = models.BooleanField(default=True)
    latest_build_id_draft = models.IntegerField(null=True, blank=True)
    live_publish_status_updated_on = models.DateTimeField(null=True, blank=True)
    draft_publish_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=zip(constants.PUBLISH_STATUSES, constants.PUBLISH_STATUSES),
    )
    draft_publish_status_updated_on = models.DateTimeField(null=True, blank=True)
    draft_last_published_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="draft_publisher",
    )

    # Unpublish fields
    unpublish_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=zip(constants.PUBLISH_STATUSES, constants.PUBLISH_STATUSES),
    )
    unpublish_status_updated_on = models.DateTimeField(null=True, blank=True)
    last_unpublished_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="unpublisher",
    )

    """
    URL path values should include the starter config prefix (ie "courses/") so that sites
    with a url_path of "courses/my-site-fall-2020" can coexist with "sites/my-site-fall-2020"
    without unique key violations being raised.
    """
    url_path = models.CharField(max_length=2048, unique=True, blank=True, null=True)

    @property
    def unpublished(self):
        """Indicate whether or not site has been unpublished"""
        return self.unpublish_status is not None

    # Google Drive fields
    gdrive_folder = models.CharField(null=True, blank=True, max_length=64)
    sync_status = models.CharField(null=True, blank=True, max_length=12)
    synced_on = models.DateTimeField(null=True, blank=True)
    sync_errors = models.JSONField(null=True, blank=True)

    @property
    def admin_group(self):
        """Get the admin group"""
        return Group.objects.filter(
            name=permissions_group_name_for_role(constants.ROLE_ADMINISTRATOR, self)
        ).first()

    @property
    def editor_group(self):
        """Get the editor group"""
        return Group.objects.filter(
            name=permissions_group_name_for_role(constants.ROLE_EDITOR, self)
        ).first()

    @property
    def collaborators(self):
        """Get all site collaborators"""
        return (
            list(self.admin_group.user_set.all())
            + [self.owner]
            + list(self.editor_group.user_set.all())
        )

    def get_site_root_path(self):
        """Get the site root url path"""
        if self.starter is None:
            return None
        site_config = SiteConfig(self.starter.config)
        if site_config:
            return site_config.root_url_path
        return ""

    def get_full_url(self, version=VERSION_LIVE):
        """Get the home page (live or draft) of the website"""
        if self.starter is None:
            # if there is no starter, there is no ability to publish
            return None

        base_url = (
            settings.OCW_STUDIO_LIVE_URL
            if version == VERSION_LIVE
            else settings.OCW_STUDIO_DRAFT_URL
        )
        url_path = self.url_path
        if url_path and self.name != settings.ROOT_WEBSITE_NAME:
            return urljoin(base_url, url_path)
        else:
            return urljoin(base_url, self.get_site_root_path())

    def get_url_path(self, with_prefix=True):
        """Get the current/potential url path, with or without site prefix"""
        url_path = self.url_path
        if not url_path:
            sitemeta = self.websitecontent_set.filter(
                type=CONTENT_TYPE_METADATA
            ).first()
            url_path = self.url_path_from_metadata(
                metadata=sitemeta.metadata if sitemeta else None
            )
        root_path = self.get_site_root_path()
        if with_prefix:
            if root_path and not url_path.startswith(root_path):
                url_path = self.assemble_full_url_path(url_path)
        elif url_path is not None:
            url_path = re.sub(f"^{root_path}/", "", url_path, 1)
        return url_path

    def assemble_full_url_path(self, path):
        """Combine site prefix and url path"""
        return "/".join(
            part.strip("/") for part in [self.get_site_root_path(), path] if part
        )

    def url_path_from_metadata(self, metadata: Dict = None):
        """Get the url path based on site config and metadata"""
        if self.starter is None:
            return None
        site_config = SiteConfig(self.starter.config)
        url_format = site_config.site_url_format
        if not url_format or self.publish_date:
            # use name for published  sites or for any sites without a `url_path` in config.
            url_format = self.name
        elif url_format:
            for section in re.findall(r"(\[.+?\])+", site_config.site_url_format) or []:
                section_type, section_field = re.sub(r"[\[\]]+", "", section).split(":")
                value = None
                if metadata:
                    value = get_dict_field(metadata, section_field)
                if not metadata or not value:
                    content = self.websitecontent_set.filter(type=section_type).first()
                    if content:
                        value = get_dict_field(content.metadata, section_field)
                if not value:
                    # Incomplete metadata required for url
                    value = section
                else:
                    value = slugify(value.replace(".", "-"))
                url_format = url_format.replace(section, value)
        return url_format

    @property
    def s3_path(self):
        """Get the S3 object path for uploaded files"""
        site_config = SiteConfig(self.starter.config)
        url_parts = [
            site_config.root_url_path,
            self.name,
        ]
        return "/".join([part.strip("/") for part in url_parts if part])

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
    """Queryset for WebsiteContent"""


class WebsiteContent(TimestampedModel, SafeDeleteModel):
    """Class for a content component of a website"""

    objects = SafeDeleteManager(WebsiteContentQuerySet)
    all_objects = SafeDeleteAllManager(WebsiteContentQuerySet)
    deleted_objects = SafeDeleteDeletedManager(WebsiteContentQuerySet)
    bulk_objects = BulkUpdateOrCreateQuerySet.as_manager()

    def upload_file_to(self, filename):
        """Return the appropriate filepath for an upload"""
        url_parts = [
            self.website.s3_path,
            f"{self.text_id.replace('-', '')}_{filename}",
        ]
        return "/".join([part for part in url_parts if part != ""])

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
    title = models.CharField(max_length=512, null=True, blank=True, db_index=True)
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
        blank=True,
        default="",
        help_text="The filename of the file that will be created from this object WITHOUT the file extension.",
    )
    dirpath = models.CharField(
        max_length=CONTENT_DIRPATH_MAX_LEN,
        null=False,
        blank=True,
        default="",
        help_text=(
            "The directory path for the file that will be created from this object."
        ),
    )
    file = models.FileField(
        upload_to=upload_file_to, editable=True, null=True, blank=True, max_length=2048
    )

    def calculate_checksum(self) -> str:
        """Returns a calculated checksum of the content"""
        return sha256(
            "\n".join(
                [
                    json.dumps(self.metadata, sort_keys=True),
                    str(self.title),
                    str(self.markdown),
                    self.type,
                    str(self.dirpath),
                    str(self.filename),
                    str(self.file.url if self.file else ""),
                ]
            ).encode("utf-8")
        ).hexdigest()

    @property
    def full_metadata(self) -> Dict:
        """Return the metadata field with file upload included"""
        file_field = self.get_config_file_field()
        s3_path = self.website.s3_path
        url_path = self.website.url_path
        full_metadata = (
            self.metadata if (self.metadata and isinstance(self.metadata, dict)) else {}
        )
        modified = False
        if file_field:
            if self.file and self.file.url:
                file_url = self.file.url
                if url_path and s3_path != url_path:
                    file_url = file_url.replace(s3_path, url_path, 1)
                full_metadata[file_field["name"]] = urlparse(file_url).path
            else:
                full_metadata[file_field["name"]] = None
            modified = True
        # Update video transcript/caption paths if they exist
        if full_metadata:
            for field in (YT_FIELD_TRANSCRIPT, YT_FIELD_CAPTIONS):
                value = get_dict_field(full_metadata, field)
                if value and url_path:
                    set_dict_field(
                        full_metadata, field, value.replace(s3_path, url_path, 1)
                    )
                    modified = True
        return full_metadata if modified else self.metadata

    def get_config_file_field(self) -> Dict:
        """Get the site config file field for the object, if any"""
        site_config = SiteConfig(self.website.starter.config)
        content_config = site_config.find_item_by_name(self.type)
        if content_config:
            return site_config.find_file_field(content_config)

    def save(self, **kwargs):  # pylint: disable=arguments-differ
        """Update dirty flags on save"""
        super().save(**kwargs)
        website = self.website
        website.has_unpublished_live = True
        website.has_unpublished_draft = True
        website.save()

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
    """Represents a starter project that contains config/templates/etc. for the desired static site"""

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
    status = models.CharField(
        max_length=30,
        choices=WEBSITE_STARTER_STATUS_CHOICES,
        default=WebsiteStarterStatus.ACTIVE,
        help_text=f"Starters with only {WEBSITE_STARTER_STATUS_CHOICES[WebsiteStarterStatus.ACTIVE]} and {WEBSITE_STARTER_STATUS_CHOICES[WebsiteStarterStatus.DEFAULT]} status will be shown while creating a new site.",
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

    def save(self, **kwargs):  # pylint: disable=arguments-differ
        """Update dirty flag on save"""
        super().save(**kwargs)
        Website.objects.filter(starter=self).update(
            has_unpublished_live=True,
            has_unpublished_draft=True,
        )

    @staticmethod
    def iter_all_config_items(website: Website) -> Iterator[Tuple[bool, ConfigItem]]:
        """
        Yields ConfigItem for all starters.

        Args:
            website (Website): The website being scanned.

        Yields:
            Iterator[Tuple[bool, ConfigItem]]: A generator where yield[0] indicates whether or not the ConfigItem
                yield[1] belongs to the starter of `website`.
        """
        if website.starter is None:
            raise ValidationError(
                f"Website {website} does not have a starter. Cannot iterate config."
            )

        all_starters = WebsiteStarter.objects.all()

        for starter in all_starters:
            for item in SiteConfig(starter.config).iter_items():
                yield website.starter == starter, item

    def __str__(self):
        return f"name='{self.name}', source={self.source}, commit={self.commit}"
