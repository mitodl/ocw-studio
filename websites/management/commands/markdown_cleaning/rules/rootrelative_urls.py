"""
WebsiteContentMarkdownCleaner rule to convert root-relative urls to resource_links
"""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_parser import (
    LinkParser,
    LinkParseResult,
    MarkdownLink,
)
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.utils import (
    ContentLookup,
    LegacyFileLookup,
    UrlSiteRelativiser,
    get_rootrelative_url_from_content,
    remove_prefix,
)
from websites.models import WebsiteContent


class RootRelativeUrlRule(PyparsingRule):
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

    @dataclass
    class ReplacementNotes:
        replacement_type: str
        is_image: bool
        same_site: bool

    Parser = LinkParser

    should_parse_regex = re.compile(r"\]\(\.?/?(course|resource)")

    def should_parse(self, text: str):
        return self.should_parse_regex.search(text)

    alias = "rootrelative_urls"

    def __init__(self) -> None:
        super().__init__()
        self.get_site_relative_url = UrlSiteRelativiser()
        self.content_lookup = ContentLookup()
        self.legacy_file_lookup = LegacyFileLookup()

    def fuzzy_find_linked_content(  # noqa: C901, PLR0911, PLR0912, PLR0915
        self, url: str
    ):
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
            msg = "Could not determine site."
            raise self.NotFoundError(msg) from error

        site_rel_path = urlparse(site_rel_url).path

        try:
            wc = self.content_lookup.find_within_site(site.uuid, site_rel_path)
            return wc, "Exact dirpath/filename match"  # noqa: TRY300
        except KeyError:
            pass

        if any(p == site_rel_path for p in ["/pages/index.htm", "/index.htm"]):
            try:
                wc = self.content_lookup.find_within_site(site.uuid, "/")
                return wc, "links to course root"  # noqa: TRY300
            except KeyError:
                pass

        try:
            prepend = "/pages"
            wc = self.content_lookup.find_within_site(
                site.uuid, prepend + site_rel_path
            )
            return wc, "prepended '/pages'"  # noqa: TRY300
        except KeyError:
            pass

        try:
            prepend = "/resources"
            remove = "/pages/video-lectures"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"  # noqa: TRY300
        except KeyError:
            pass
        try:
            prepend = "/resources"
            remove = "/pages/video-and-audio-classes"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"  # noqa: TRY300
        except KeyError:
            pass

        try:
            prepend = "/resources"
            remove = "/videos"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"  # noqa: TRY300
        except KeyError:
            pass

        try:
            prepend = "/video_galleries"
            remove = "/pages"
            resource_url = prepend + remove_prefix(site_rel_path, remove)
            wc = self.content_lookup.find_within_site(site.uuid, resource_url)
            return wc, f"removed '{remove}', prepended '{prepend}'"  # noqa: TRY300
        except KeyError:
            pass

        try:
            match = self.legacy_file_lookup.find(site.uuid, site_rel_path)
            return match, "unique file match"  # noqa: TRY300
        except self.legacy_file_lookup.MultipleMatchError as error:
            raise self.NotFoundError(error)  # noqa: B904, TRY200
        except KeyError as error:
            if "." in site_rel_path[-8:]:
                msg = "Content not found. Perhaps unmigrated file"
                raise self.NotFoundError(msg) from error
            msg = "Content not found."
            raise self.NotFoundError(msg) from error

    def replace_match(
        self,
        s,  # noqa: ARG002
        l,  # noqa: ARG002, E741
        toks: LinkParseResult,
        website_content: WebsiteContent,
    ) -> str:
        Notes = self.ReplacementNotes
        original_text = toks.original_text
        destination = toks.link.destination
        url = urlparse(destination)
        is_image = toks.link.is_image
        text = self.parser.transform_string(toks.link.text)
        link = MarkdownLink(text=text, is_image=is_image, destination=destination)

        if not re.match(R".?/?(course|resource)", url.path):
            return link.to_markdown(), Notes("Not rootrelative link", None, None)

        try:
            linked_content, note = self.fuzzy_find_linked_content(url.path)
        except self.NotFoundError as error:
            note = str(error)
            return link.to_markdown(), Notes(note, is_image, same_site=None)

        same_site = linked_content.website_id == website_content.website_id
        fragment = url.fragment

        can_be_shortcode = (
            same_site
            and "![" not in link.text
            and "{{%" not in link.text
            and "{{<" not in link.text
        )
        notes = Notes(note, is_image, same_site)
        if can_be_shortcode:
            try:
                if is_image:
                    shortcode = ShortcodeTag.resource(uuid=linked_content.text_id)
                else:
                    shortcode = ShortcodeTag.resource_link(
                        uuid=linked_content.text_id, text=text, fragment=fragment
                    )
                return shortcode.to_hugo(), notes
            except ValueError:
                # This happens with within-site links to the homepage.
                # The text_id of the resource is "sitemetadata", which is not
                # a uuid. The resource link shortcode probably works in this
                # case, but there are only 3 of these, so let's not worry about
                # it. Plus, keeping resource_links as true UUIDs will be nice
                # if we implement cross-site resource_links down the road.
                return original_text, Notes(
                    f"bad uuid: {linked_content.text_id}", is_image, same_site
                )

        if is_image:
            # Cross-site images would be problematic because
            # - we want to link to the actual image, not the "container" page
            # - which we probably could do, but don't have code to handle at the moment.
            #
            # In practice, there appear to be no cross-site images, so let's not
            # worry about this for now.
            return original_text, notes

        destination = get_rootrelative_url_from_content(linked_content)
        if fragment:
            destination = destination + "#" + fragment

        new_link = MarkdownLink(
            text=text,
            destination=destination,
            is_image=is_image,
        )

        return new_link.to_markdown(), notes
