from dataclasses import dataclass
from functools import partial
from urllib.parse import urlparse

from django.conf import settings
from django.utils.text import slugify

from main.utils import uuid_string
from websites.constants import CONTENT_TYPE_EXTERNAL_RESOURCE
from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.utils import StarterSiteConfigLookup
from websites.models import WebsiteContent
from websites.utils import get_valid_base_filename


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

        metadata = config.generate_item_metadata(
            CONTENT_TYPE_EXTERNAL_RESOURCE, use_defaults=True
        )
        metadata["external_url"] = toks.link.destination

        text_id = uuid_string()
        link_text = toks.link.text
        config_item = config.find_item_by_name(CONTENT_TYPE_EXTERNAL_RESOURCE)

        resource, _ = WebsiteContent.objects.get_or_create(
            metadata=metadata,
            dirpath=config_item.file_target,
            website=website_content.website,
            type=CONTENT_TYPE_EXTERNAL_RESOURCE,
            defaults={
                "text_id": text_id,
                "title": link_text,
                "is_page_content": config.is_page_content(config_item),
                "filename": slugify(
                    get_valid_base_filename(
                        f"{link_text}_{text_id}",  # to avoid collisions
                        CONTENT_TYPE_EXTERNAL_RESOURCE,
                    ),
                    allow_unicode=True,
                ),
            },
        )

        shortcode = ShortcodeTag.resource_link(resource.text_id, link_text)

        return shortcode.to_hugo(), self.ReplacementNotes(note="replaced successfully")

    def should_parse(self, text: str):
        """Should the text be parsed?

        If the text does not contain '](', then it definitely does not have
        markdown links.
        """  # noqa: D401
        return "](" in text
