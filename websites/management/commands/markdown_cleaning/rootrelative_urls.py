"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import re
import os
from dataclasses import dataclass
from urllib.parse import urlparse

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
            site, site_rel_url = self.get_site_relative_url(url)
        except ValueError:
            raise self.NotFoundError("Could not determine site.")

        site_rel_path = urlparse(site_rel_url).path

        try:
            wc = self.content_lookup.find(site.uuid, site_rel_path)
            return site, wc , "Exact dirpath/filename match"
        except KeyError:
            pass
        
        try:
            prepend = '/pages'
            wc = self.content_lookup.find(site.uuid, prepend + site_rel_path)
            return site, wc, "prepended '/pages'"
        except KeyError:
            pass

        try:
            prepend = '/resources'
            remove = '/pages/video-lectures'
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find(site.uuid, resource_url)
            return site, wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass
        try:
            prepend = '/resources'
            remove = '/pages/video-and-audio-classes'
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find(site.uuid, resource_url)
            return site, wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            prepend = '/resources'
            remove = '/videos'
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find(site.uuid, resource_url)
            return site, wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass
            
        try:
            prepend = '/video_galleries'
            remove = '/pages'
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find(site.uuid, resource_url)
            return site, wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            _, legacy_filename = os.path.split(site_rel_path)
            file_matches = self.legacy_file_lookup.find(site.uuid, legacy_filename)
            if len(file_matches) == 1: 
                return site, file_matches[0], "unique file match"
            return site, file_matches[0], f"multiple file matches ({len(file_matches)}); took first"
        except KeyError:
            if '.' in site_rel_path[-8:]:
                raise self.NotFoundError("Content not found. Perhaps unmigrated file")
            raise self.NotFoundError("Content not found.")

    def __call__(self, match: re.Match, website_content: WebsiteContent) -> str:
        Notes = self.ReplacementNotes
        original_text = match[0]
        url = match.group('url')
        image_prefix = match.group('image_prefix')
        is_image = image_prefix == '!'
        title = match.group('title')

        try:
            linked_site, linked_content, note = self.find_linked_content(url)
        except self.NotFoundError as error:
            note = str(error)
            return original_text, Notes(note, is_image, same_site=False)

        same_site = linked_content.website_id == website_content.website_id
        fragment = urlparse(url).fragment
        
        notes = Notes(note, is_image, same_site)
        if same_site:
            uuid = linked_content.text_id

            if is_image:
                replacement = f'{{{{< resource {uuid} "{title}" >}}}}'
            elif fragment:
                replacement = f'{{{{% resource_link {uuid} "{title}" "#{fragment}" %}}}}'
            else:
                replacement = f'{{{{% resource_link {uuid} "{title}" %}}}}'
            return replacement, notes

        new_url_pieces = ['/courses', linked_site.name, linked_content.dirpath, linked_content.filename]
        new_url = "/".join(p for p in new_url_pieces if p)

        if linked_content.dirpath:
            new_url
        if fragment:
            new_url += f"#{fragment}"
        
        replacement = f"{image_prefix}[{title}]({new_url})"

        return replacement, notes