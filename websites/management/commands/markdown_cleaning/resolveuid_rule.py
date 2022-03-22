from uuid import UUID
from functools import partial
from dataclasses import dataclass
from typing import Union

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_grammar import (
    LinkParser,
    MarkdownLink,
)
from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeTag
)
from websites.management.commands.markdown_cleaning.utils import (
    remove_prefix,
    ContentLookup,
    get_rootrelative_url_from_content
)


class LinkLoggingRule(PyparsingRule):
    """
    Find all links in all Websitecontent markdown bodies plus some metadata
    fields and log information about them to a csv.
    """

    alias = "link_logging"

    Parser = LinkParser

    fields = [
        'markdown',
        # There is like 1 instance of resolveuid occurs in one metadata field.
        # Going to fix that manually to ensure it is a root-relative link
        # and not a shortcode... avoids a conditional here.
    ]

    @dataclass
    class ReplacementNotes:
        is_image: str
        linked_site_name: Union[str, None] = None
        linked_content_uuid: Union[str, None] = None
        error: str = ''

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def replace_match(self, s: str, l: int, toks, website_content):
        link: MarkdownLink = toks.link
        original_text = toks.original_text
        notes = partial(self.ReplacementNotes, is_image=link.is_image)

        try:
            uuid = UUID(remove_prefix(link.destination, './resolveuid/'))
        except ValueError as error:
            return original_text, notes(error=str(error))

        try:
            linked_content = self.content_lookup.find_by_uuid(uuid)
        except KeyError as error:
            return original_text, notes(error=str(error))

        notes = notes(
            linked_content_uuid=linked_content.text_id,
            linked_site_name=linked_content.website.name
        )

        if linked_content.website_id == website_content.website_id:
            if link.is_image:
                shortcode = ShortcodeTag(
                    name='resource',
                    args=[str(uuid)],
                    percent_delimiters=False
                )
            else:
                shortcode = ShortcodeTag(
                    name='resource_link',
                    args=[str(uuid), link.text],
                    percent_delimiters=True
                )
            return shortcode.to_hugo, notes
        else:
            new_link = MarkdownLink(
                text=link.text,
                destination=get_rootrelative_url_from_content(linked_content),
                is_image=link.is_image,
                title=link.title # should be empty, resolveuid links don't have this.
            )
            return new_link.to_markdown(), notes

    def should_parse(self, text: str):
        """Should the text be parsed?
        
        If the text does not contain '](', then it definitely does not have
        markdown links.
        """
        return 'resolveuid' in text
