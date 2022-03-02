"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import re
import os
from dataclasses import dataclass

from websites.models import WebsiteContent
from websites.management.commands.markdown_cleaning.utils import (
    UrlSiteRelativiser,
    ContentLookup,
    LegacyFileLookup
)
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)

def remove_prefix(string: str, prefix: str):
    if string.startswith(prefix):
        return string[len(prefix):]
    return string

class RootRelativeUrlRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    @dataclass
    class ReplacementNotes:
        replacement_type: str = ''

    regex = (
        r"(?P<image_prefix>!?)"             # optional leading "!" to determine if it's a link or an image
        + r"\\?\["                          # match title opening "[" (or "\[" in case corrupted by studio save)
        + r"(?P<title>[^\[\]\<\>\n]*?)"     # capture the title
        + r"\\?\]"                          # title closing "]" (or "\]")
        + r"\("                             # url open
        + r"/?"                             # optional, non-captured leading "/"
        + r"(?P<url>(course|resource).*?)"  # capture the url, but only if it's course/ or resoruce/... we don't want links to wikipedia.
        + r"\)"                             # url close
    )

    alias = "rootrelative_urls"

    def __init__(self) -> None:
        self.get_site_relative_url = UrlSiteRelativiser()
        self.content_lookup = ContentLookup()
        self.legacy_file_lookup = LegacyFileLookup()

    def __call__(self, match: re.Match, website_content: WebsiteContent) -> str:
        Notes = self.ReplacementNotes

        original_text = match[0]
        url = match.group('url')

        try:
            link_site_id, site_rel_url = self.get_site_relative_url(url)
        except ValueError:
            return original_text, Notes('Site does not exist')
        
        use_shortcode = link_site_id == website_content.website_id
        is_image = match.group('image_prefix') == '!'

        try:
            self.content_lookup.find(link_site_id, site_rel_url)
            return original_text, Notes("Exact dirpath/filename match")
        except KeyError:
            pass
        
        try:
            prepend = '/pages'
            self.content_lookup.find(link_site_id, prepend + site_rel_url)
            return original_text, Notes("prepended '/pages'")
        except KeyError:
            pass


        try:
            prepend = '/resources'
            remove = '/pages/video-lectures'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            self.content_lookup.find(link_site_id, resource_url)
            return original_text, Notes(f"removed '{remove}', prepended '{prepend}'")
        except KeyError:
            pass
        try:
            prepend = '/resources'
            remove = '/pages/video-and-audio-classes'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            self.content_lookup.find(link_site_id, resource_url)
            return original_text, Notes(f"removed '{remove}', prepended '{prepend}'")
        except KeyError:
            pass

        try:
            prepend = '/resources'
            remove = '/videos'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            self.content_lookup.find(link_site_id, resource_url)
            return original_text, Notes(f"removed '{remove}', prepended '{prepend}'")
        except KeyError:
            pass
            
        try:
            prepend = '/video_galleries'
            remove = '/pages'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            self.content_lookup.find(link_site_id, resource_url)
            return original_text, Notes(f"removed '{remove}', prepended '{prepend}'")
        except KeyError:
            pass

        try:
            _, legacy_filename = os.path.split(site_rel_url)
            self.legacy_file_lookup.find(link_site_id, legacy_filename)
            return original_text, Notes("unique file match")
        except LegacyFileLookup.MultipleMatches:
            return original_text, Notes("duplicate file matches")
        except KeyError:
            if '.' in site_rel_url[-8:]:
                return original_text, Notes("???: Probably unmigrated file")
            return original_text, Notes("???")

