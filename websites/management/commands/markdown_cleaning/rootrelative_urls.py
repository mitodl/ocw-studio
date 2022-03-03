"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import re
import os
from dataclasses import dataclass

from websites.models import WebsiteContent
from websites.management.commands.markdown_cleaning.utils import (
    remove_prefix,
    UrlSiteRelativiser,
    ContentLookup,
    LegacyFileLookup
)
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
class RootRelativeUrlRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    class NotFoundError(Exception):
        pass

    @dataclass
    class ReplacementNotes:
        replacement_type: str
        is_image: bool
        same_site: bool

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

    def find_linked_content(self, url: str):
        try:
            site_id, site_rel_url = self.get_site_relative_url(url)
        except ValueError:
            raise self.NotFoundError("Could not determine site.")

        try:
            wc = self.content_lookup.find(site_id, site_rel_url)
            return wc , "Exact dirpath/filename match"
        except KeyError:
            pass
        
        try:
            prepend = '/pages'
            wc = self.content_lookup.find(site_id, prepend + site_rel_url)
            return wc, "prepended '/pages'"
        except KeyError:
            pass

        try:
            prepend = '/resources'
            remove = '/pages/video-lectures'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            wc = self.content_lookup.find(site_id, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass
        try:
            prepend = '/resources'
            remove = '/pages/video-and-audio-classes'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            wc = self.content_lookup.find(site_id, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            prepend = '/resources'
            remove = '/videos'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            wc = self.content_lookup.find(site_id, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass
            
        try:
            prepend = '/video_galleries'
            remove = '/pages'
            resource_url = prepend + remove_prefix(site_rel_url, remove)
            wc = self.content_lookup.find(site_id, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            _, legacy_filename = os.path.split(site_rel_url)
            file_matches = self.legacy_file_lookup.find(site_id, legacy_filename)
            if len(file_matches) == 1: 
                return file_matches[0], "unique file match"
            return file_matches[0], f"multiple file matches ({len(file_matches)}); took first"
        except KeyError:
            if '.' in site_rel_url[-8:]:
                raise self.NotFoundError("Content not found. Perhaps unmigrated file")
            raise self.NotFoundError("Content not found.")

    def __call__(self, match: re.Match, website_content: WebsiteContent) -> str:
        Notes = self.ReplacementNotes
        original_text = match[0]
        url = match.group('url')
        is_image = match.group('image_prefix') == '!'

        try:
            linked_content, note = self.find_linked_content(url)
        except self.NotFoundError as error:
            note = str(error)
            return original_text, Notes(note, is_image, same_site=False)

        same_site = linked_content.website_id == website_content.website_id

        return original_text, Notes(note, is_image, same_site)

        # cross-site index sites
        # other cross-site links
        # same-site images
        # same-site links