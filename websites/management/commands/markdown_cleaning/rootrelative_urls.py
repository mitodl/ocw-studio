"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    LegacyFileLookup,
    UrlSiteRelativiser,
    get_rootrelative_url_from_content,
    remove_prefix,
)
from websites.models import WebsiteContent


class RootRelativeUrlRule(RegexpCleanupRule):
    """
    Fix rootrelative urls, converting to shortcodes where possible.

    When Legacy OCW content was migrated to OCW Next, many migrated links were
    root-relative and possibly broken. For example:

    The link:
        [Filtration](/resources/res-5-0001-digital-lab-techniques-manual-spring-2007/videos/filtration/)
    should be:
        [Filtration](/courses/res-5-0001-digital-lab-techniques-manual-spring-2007/resources/filtration)

    The cleanup rule
        1. Finds rootrelative links/images in markdown
        2. Attempts to find content matching that link/image
        3. If content is found AND the link/image is within-site:
            - changes links to resource_links and images to resources
        4. If content is found AND the link/image is cross-site:
            - keeps the link rootrelative, but fixes it to work in OCW (like the
                5-0001 exmple above)

    Changes are only ever made if matching content for the link is found!
    """

    class NotFoundError(Exception):
        """Thrown when no content math for a url is found."""

        pass

    @dataclass
    class ReplacementNotes:
        replacement_type: str
        is_image: bool
        same_site: bool

    regex = (
        r"(?P<image_prefix>!?)"  # optional leading "!" to determine if it's a link or an image
        + r"\\?\["  # match title opening "[" (or "\[" in case corrupted by studio save)
        + r"(?P<title>[^\[\]\<\>\n]*?)"  # capture the title
        + r"\\?\]"  # title closing "]" (or "\]")
        + r"\("  # url open
        + r"/?"  # optional, non-captured leading "/"
        + r"(?P<url>(course|resource).*?)"  # capture the url, but only if it's course/ or resoruce/... we don't want links to wikipedia.
        + r"\)"  # url close
    )

    alias = "rootrelative_urls"

    def __init__(self) -> None:
        super().__init__()
        self.get_site_relative_url = UrlSiteRelativiser()
        self.content_lookup = ContentLookup()
        self.legacy_file_lookup = LegacyFileLookup()

    def fuzzy_find_linked_content(self, url: str):
        """
        Given a possibly-broken, root-relative URL, find matching content.

        Example:
            /resources/res-5-0001-digital-lab-techniques-manual-spring-2007/videos/filtration/
        Matches:
            WebsiteContent(
                website=Website(name="res-5-0001-digital-lab-techniques-manual-spring-2007"),
                filename="filtration",
                dirpath="content/resources",
            )
        """

        try:
            site, site_rel_url = self.get_site_relative_url(url)
        except ValueError as error:
            raise self.NotFoundError("Could not determine site.") from error

        site_rel_path = urlparse(site_rel_url).path

        try:
            wc = self.content_lookup.find_within_site(site.uuid, site_rel_path)
            return wc, "Exact dirpath/filename match"
        except KeyError:
            pass

        if any(p == site_rel_path for p in ['/pages/index.htm', '/index.htm']):
            try:
                wc = self.content_lookup.find_within_site(site.uuid, '/')
                return wc, "links to course root"
            except KeyError:
                pass


        try:
            prepend = "/pages"
            wc = self.content_lookup.find_within_site(
                site.uuid, prepend + site_rel_path
            )
            return wc, "prepended '/pages'"
        except KeyError:
            pass

        try:
            prepend = "/resources"
            remove = "/pages/video-lectures"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass
        try:
            prepend = "/resources"
            remove = "/pages/video-and-audio-classes"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            prepend = "/resources"
            remove = "/videos"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            prepend = "/video_galleries"
            remove = "/pages"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"
        except KeyError:
            pass

        try:
            _, legacy_filename = os.path.split(site_rel_path)
            match = self.legacy_file_lookup.find(site.uuid, legacy_filename)
            return match, "unique file match"
        except self.legacy_file_lookup.MultipleMatchError as error:
            raise self.NotFoundError(error)
        except KeyError as error:
            if "." in site_rel_path[-8:]:
                raise self.NotFoundError(
                    "Content not found. Perhaps unmigrated file"
                ) from error
            raise self.NotFoundError("Content not found.") from error

    def replace_match(self, match: re.Match, website_content: WebsiteContent) -> str:
        Notes = self.ReplacementNotes
        original_text = match[0]
        url = match.group("url")
        image_prefix = match.group("image_prefix")
        is_image = image_prefix == "!"
        title = match.group("title")

        try:
            linked_content, note = self.fuzzy_find_linked_content(url)
        except self.NotFoundError as error:
            note = str(error)
            return original_text, Notes(note, is_image, same_site=False)

        same_site = linked_content.website_id == website_content.website_id
        fragment = urlparse(url).fragment

        notes = Notes(note, is_image, same_site)
        if same_site:
            uuid = linked_content.text_id

            if is_image:
                replacement = f"{{{{< resource {uuid} >}}}}"
            elif fragment:
                replacement = (
                    f'{{{{% resource_link {uuid} "{title}" "#{fragment}" %}}}}'
                )
            else:
                replacement = f'{{{{% resource_link {uuid} "{title}" %}}}}'
            return replacement, notes

        if is_image:
            return original_text, notes

        new_url = get_rootrelative_url_from_content(linked_content)

        if fragment:
            new_url += f"#{fragment}"

        replacement = f"{image_prefix}[{title}]({new_url})"

        return replacement, notes
