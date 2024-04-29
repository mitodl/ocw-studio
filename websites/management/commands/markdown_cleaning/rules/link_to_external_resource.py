from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from django.conf import settings
from django.utils.text import slugify

from main.utils import uuid_string
from websites.constants import CONTENT_FILENAME_MAX_LEN, CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
    PyparsingRule,
)
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.utils import StarterSiteConfigLookup
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig
from websites.utils import get_valid_base_filename


def is_ocw_domain_url(url: str) -> bool:
    """Return True `url` has an ocw domain."""
    parsed_url = urlparse(url)
    return parsed_url.netloc == "ocw.mit.edu"


def build_external_resource(
    site_config: SiteConfig,
    website: Website,
    title: str,
    url: str,
) -> WebsiteContent:
    """
    Build a WebsiteContent object for an external-resource.

    This does not save the object to the database.
    """
    metadata = site_config.generate_item_metadata(
        CONTENT_TYPE_EXTERNAL_RESOURCE, use_defaults=True
    )
    metadata["external_url"] = url
    metadata["has_external_license_warning"] = not is_ocw_domain_url(url)

    # title is a special field. By default the value of title
    # is stored in `website_content.title` field. Having both,
    # `website_content.title` and `website_content.metadata['title']`,
    # not only confuses the developer but also some UI components like
    # navmenu.
    metadata.pop("title", None)

    config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)
    text_id = uuid_string()

    filename = slugify(
        get_valid_base_filename(
            f"{title}_{text_id}",  # to avoid collisions
            CONTENT_TYPE_EXTERNAL_RESOURCE,
        ),
        allow_unicode=True,
    )

    if len(filename) > CONTENT_FILENAME_MAX_LEN:
        # trim excess from the middle, preserving the uuid
        filename = filename[: CONTENT_FILENAME_MAX_LEN - 36] + filename[-36:]

    return WebsiteContent(
        metadata=metadata,
        dirpath=config_item.file_target,
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        text_id=text_id,
        title=title[:512],
        is_page_content=site_config.is_page_content(config_item),
        filename=filename,
    )


def get_or_build_external_resource(
    website: WebsiteContent,
    site_config: SiteConfig,
    url: str,
    title: str,
) -> WebsiteContent:
    """
    Find or build a WebsiteContent object for an external resource.

    This method does not create new entities in the database.
    """
    config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)

    resource = WebsiteContent.objects.filter(
        metadata__external_url=url,
        dirpath=config_item.file_target,
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
    ).first()

    if resource is None:
        resource = build_external_resource(
            site_config=site_config,
            website=website,
            title=title,
            url=url,
        )

    return resource


class LinkToExternalResourceRule(PyparsingRule):
    """
    Converts links to external resources by replacing
    markdown links with resource_link shortcodes.

    Creates new WebsiteContent objects for unqiue links.

    Example:
    From:
    ```
    [OCW](https://ocw.mit.edu)
    [OCW clone](https://ocw.mit.edu)
    [OCW same but not so](https://ocw.mit.edu#fragment)
    ```

    To:
    ```
    {{% resource_link "f3d0ebae-7083-4524-9b93-f688537a0317" "OCW" %}}
    {{% resource_link "f3d0ebae-7083-4524-9b93-f688537a0317" "OCW clone" %}}
    {{% resource_link "d3d0ebae-7083-3453-7b92-a688537a0276" "OCW same but not so" %}}
    ```
    and two new WebsiteContent objects.
    """

    alias = "link_to_external_resource"

    Parser = partial(LinkParser, recursive=True)

    fields = [
        "markdown",
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    @dataclass
    class ReplacementNotes:
        note: str
        url: str = ""
        external_resource: str = ""
        has_external_license_warning: bool = True

    def __init__(self) -> None:
        super().__init__()
        self.starter_lookup = StarterSiteConfigLookup()

    def replace_match(
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: ARG002, E741
        toks: LinkParseResult,
        website_content: WebsiteContent,
    ):
        link = toks.link
        try:
            url = urlparse(link.destination)
        except ValueError:
            return toks.original_text, self.ReplacementNotes(note="invalid url")

        if not url.scheme.startswith("http"):
            return toks.original_text, self.ReplacementNotes(note="not external")

        if toks.link.is_image:
            return toks.original_text, self.ReplacementNotes(note="is image")

        starter_id = website_content.website.starter_id
        starter = self.starter_lookup.get_starter(starter_id)

        if starter.slug != settings.OCW_COURSE_STARTER_SLUG:
            return toks.original_text, self.ReplacementNotes(note="not course content")

        config = self.starter_lookup.get_config(starter_id)
        link_text = toks.link.text

        resource = get_or_build_external_resource(
            website=website_content.website,
            site_config=config,
            url=toks.link.destination,
            title=link_text,
        )

        if self.options.get("commit", True):
            resource.save()

        shortcode = ShortcodeTag.resource_link(resource.text_id, link_text)

        return shortcode.to_hugo(), self.ReplacementNotes(
            note="replaced successfully",
            url=toks.link.destination,
            external_resource=resource.text_id,
            has_external_license_warning=resource.metadata[
                "has_external_license_warning"
            ],
        )

    def should_parse(self, text: str) -> bool:
        """
        Return True if `text` may contain a markdown link.
        """
        return "](" in text


class NavItemToExternalResourceRule(MarkdownCleanupRule):
    """
    Convert navigation menu's external links to external resources.

    Creates a new external resource for each link.

    Example
        From:

        ```
        [
            {
                "name": "Name",
                "url": "https://ocw.mit.edu",
                "weight": 10,
                "identifier": "external--760432549-1711617249481"
            }
        ]
        ```

        To:

        ```
        [
            {
                "name": "Name",
                "weight": 10,
                "identifier": "f3d0ebae-7083-4524-9b93-f688537a0317"
            }
        ]
        ```
        and a new corresponding WebsiteContent object.
    """

    alias = "nav_item_to_external_resource"

    fields = [
        "metadata.leftnav",
    ]

    @dataclass
    class ReplacementNotes:
        url: str
        external_resource: str
        has_external_license_warning: bool

    def __init__(self) -> None:
        super().__init__()
        self.starter_lookup = StarterSiteConfigLookup()

    def generate_item_replacement(
        self, website_content: WebsiteContent, item: dict
    ) -> tuple[dict, WebsiteContent]:
        """
        Generate a new item linked to an external resource using
        the values from `item`.
        """
        url = item.get("url", "")
        link_text = item.get("name", url)
        starter_id = website_content.website.starter_id
        site_config = self.starter_lookup.get_config(starter_id)

        resource = build_external_resource(
            website=website_content.website,
            site_config=site_config,
            url=url,
            title=link_text,
        )

        if self.options.get("commit", True):
            resource.save()

        item_replacement = {
            **item,
            "identifier": str(resource.text_id),
        }

        del item_replacement["url"]

        return item_replacement, resource

    def transform_text(
        self, website_content: WebsiteContent, text: list[dict], on_match
    ) -> str:
        """
        Return new text to replace `text`.
        """
        nav_items = text
        transformed_items = []
        id_replacements = {}

        for item in nav_items:
            if item.get("identifier", "").startswith("external") and item.get("url"):
                item_replacement, resource = self.generate_item_replacement(
                    website_content, item
                )

                notes = self.ReplacementNotes(
                    url=item["url"],
                    external_resource=str(resource.text_id),
                    has_external_license_warning=resource.metadata[
                        "has_external_license_warning"
                    ],
                )

                on_match(item, item_replacement, website_content, notes)

                transformed_items.append(item_replacement)
                id_replacements[item["identifier"]] = item_replacement["identifier"]
            else:
                transformed_items.append(item)

        # when external links are changed into external resources,
        # their `identifier` property changes.
        # The snippet below updates the `parent` property to use
        # the new identifiers.
        for item in transformed_items:
            if item.get("parent") and id_replacements.get(item["parent"]):
                item["parent"] = id_replacements[item["parent"]]

        return transformed_items
