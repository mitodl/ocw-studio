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


def get_or_create_external_resource(
    website_content, site_config, url, link_text, should_commit
):
    metadata = site_config.generate_item_metadata(
        CONTENT_TYPE_EXTERNAL_RESOURCE, use_defaults=True
    )
    metadata["external_url"] = url

    text_id = uuid_string()
    config_item = site_config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)

    resource = WebsiteContent.objects.filter(
        metadata__external_url=url,
        dirpath=config_item.file_target,
        website=website_content.website,
        type=CONTENT_TYPE_EXTERNAL_RESOURCE,
    ).first()
    needs_creation = False

    if resource is None:
        needs_creation = True
        resource = WebsiteContent(
            metadata=metadata,
            dirpath=config_item.file_target,
            website=website_content.website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            text_id=text_id,
            title=link_text,
            is_page_content=site_config.is_page_content(config_item),
            filename=slugify(
                get_valid_base_filename(
                    f"{link_text}_{text_id}",  # to avoid collisions
                    CONTENT_TYPE_EXTERNAL_RESOURCE,
                ),
                allow_unicode=True,
            ),
        )

    if needs_creation and should_commit:
        resource.save()

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

        resource = get_or_create_external_resource(
            website_content=website_content,
            site_config=config,
            url=toks.link.destination,
            link_text=link_text,
            should_commit=self.options.get("commit", True),
        )

        shortcode = ShortcodeTag.resource_link(resource.text_id, link_text)

        return shortcode.to_hugo(), self.ReplacementNotes(note="replaced successfully")

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

    def __init__(self) -> None:
        super().__init__()
        self.starter_lookup = StarterSiteConfigLookup()

    def generate_external_resource(self, website_content, item):
        url = item.get("url", "")
        link_text = item.get("name", url)

        starter_id = website_content.website.starter_id
        config = self.starter_lookup.get_config(starter_id)

        resource = get_or_create_external_resource(
            website_content=website_content,
            site_config=config,
            url=url,
            link_text=link_text,
            should_commit=self.options.get("commit", True),
        )

        new_item = {
            **item,
            "identifier": str(resource.text_id),
        }

        if url:
            del new_item["url"]

        return new_item

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
                item_repalcement = self.generate_external_resource(
                    website_content, item
                )
                notes = self.ReplacementNotes()

                on_match(item, item_repalcement, website_content, notes)

                transformed_items.append(item_repalcement)
                id_replacements[item["identifier"]] = item_repalcement["identifier"]
            else:
                transformed_items.append(item)

        for item in transformed_items:
            if (
                item.get("parent") is not None
                and id_replacements.get(item["parent"]) is not None
            ):
                item["parent"] = id_replacements[item["parent"]]

        return transformed_items
