from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from django.conf import settings
from django.utils.text import slugify

from main.utils import uuid_string
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
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
from websites.models import WebsiteContent
from websites.utils import get_valid_base_filename


def is_ocw_domain_url(url: str):
    parsed_url = urlparse(url)
    return parsed_url.netloc == "ocw.mit.edu"


def build_external_resource(
    site_config,
    website,
    title,
    url,
):
    metadata = site_config.generate_item_metadata(
        CONTENT_TYPE_EXTERNAL_RESOURCE, use_defaults=True
    )
    metadata["external_url"] = url
    metadata["has_external_licence_warning"] = not is_ocw_domain_url(url)

    config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)
    text_id = uuid_string()

    return WebsiteContent(
        metadata=metadata,
        dirpath=config_item.file_target,
        website=website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
        text_id=text_id,
        title=title,
        is_page_content=site_config.is_page_content(config_item),
        filename=slugify(
            get_valid_base_filename(
                f"{title}_{text_id}",  # to avoid collisions
                CONTENT_TYPE_EXTERNAL_RESOURCE,
            ),
            allow_unicode=True,
        ),
    )


def get_or_build_external_resource(
    website,
    site_config,
    url,
    title,
):
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
    Convert links to external resources.
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
        has_external_license_warning: bool = ""

    def __init__(self) -> None:
        super().__init__()
        self.starter_lookup = StarterSiteConfigLookup()

    def replace_match(
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: E741, ARG002
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
            url=url,
            external_resource=resource,
            has_external_license_warning=resource.metadata[
                "has_external_license_warning"
            ],
        )

    def should_parse(self, text: str):
        """Should the text be parsed?

        If the text does not contain '](', then it definitely does not have
        markdown links.
        """  # noqa: D401
        return "](" in text


class NavItemToExternalResourceRule(MarkdownCleanupRule):
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

    def generate_item_replacement(self, website_content: WebsiteContent, item):
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
        self, website_content: WebsiteContent, text: list, on_match
    ) -> str:
        nav_items = text
        transformed_items = []
        id_replacements = {}

        for item in nav_items:
            if (
                item.get("identifier", "").startswith("external")
                and item.get("url") is not None
            ):
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

        for item in transformed_items:
            if (
                item.get("parent") is not None
                and id_replacements.get(item["parent"]) is not None
            ):
                item["parent"] = id_replacements[item["parent"]]

        return transformed_items
