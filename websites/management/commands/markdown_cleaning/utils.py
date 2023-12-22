"""Replace baseurl-based links with resource_link shortcodes."""
import importlib
import os
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from main.utils import is_valid_uuid
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.site_config_api import SiteConfig

filepath_migration = importlib.import_module(
    "websites.migrations.0023_website_content_filepath"
)
CONTENT_FILENAME_MAX_LEN = filepath_migration.CONTENT_FILENAME_MAX_LEN
CONTENT_DIRPATH_MAX_LEN = filepath_migration.CONTENT_DIRPATH_MAX_LEN


def remove_prefix(string: str, prefix: str):
    if string.startswith(prefix):
        return string[len(prefix) :]
    return string


def get_rootrelative_url_from_content(content: WebsiteContent):
    dirpath = remove_prefix(content.dirpath, "content/")
    filename = "" if content.filename == "_index" else content.filename
    pieces = [content.website.url_path, dirpath, filename]
    return "/" + "/".join(p for p in pieces if p)


class StarterSiteConfigLookup:
    """
    Utility to get site config.
    """

    def __init__(self) -> None:
        starters = WebsiteStarter.objects.all()

        self._configs = {starter.id: SiteConfig(starter.config) for starter in starters}
        self._config_items = {
            starter_id: list(config.iter_items())
            for starter_id, config in self._configs.items()
        }

    def get_config(self, starter_id):
        return self._configs[starter_id]

    def config_items(self, starter_id):
        return self._config_items[starter_id]


class ContentLookup:
    """
    Helps find content by website_id and a valid OCW-Next url.
    """

    def __init__(self):
        website_contents = WebsiteContent.all_objects.all().prefetch_related("website")
        websites = Website.objects.all()

        self.website_contents = {
            (wc.website_id, wc.dirpath, wc.filename): wc for wc in website_contents
        }
        self.metadata = {
            wc.website_id: wc for wc in website_contents if wc.type == "sitemetadata"
        }
        self.websites = {wc.website.name: wc.website_id for wc in website_contents}
        self.websites_by_url_path = {website.url_path: website for website in websites}

        self.by_uuid = {
            UUID(wc.text_id): wc for wc in website_contents if is_valid_uuid(wc.text_id)
        }

    def __str__(self):
        return self.website_contents.__str__()

    @staticmethod
    def standardize_dirpath(content_relative_dirpath):
        """Get dirpath in our database format (see migration 0023)"""
        return "content" + content_relative_dirpath[0:CONTENT_DIRPATH_MAX_LEN]

    @staticmethod
    def standardize_filename(filename):
        """Get filename in our database format (see migration 0023)"""
        return filename[0:CONTENT_FILENAME_MAX_LEN].replace(".", "-")

    def find_by_uuid(self, uuid: UUID) -> WebsiteContent:
        """Retrieve a content object by its UUID"""
        return self.by_uuid[uuid]

    def find_website_by_url_path(self, url_path: str):
        """Retrieve a website object by its url_path"""
        return self.websites_by_url_path[url_path]

    def find(
        self, root_relative_path: str, base_site: Optional[Website] = None
    ) -> WebsiteContent:
        standardized_path = root_relative_path.strip("/") + "/"
        baseurl_prefix = R"{{< baseurl >}}"
        if base_site is not None and standardized_path.startswith(R"{{< baseurl >}}"):
            standardized_path = f"courses/{base_site.name}" + remove_prefix(
                standardized_path, baseurl_prefix
            )

        if not standardized_path.startswith("courses/"):
            msg = f"Content for '{standardized_path}' not found"
            raise KeyError(msg)
        site_name = standardized_path.split("/")[1]

        relative_path = remove_prefix(standardized_path, f"courses/{site_name}")

        try:
            site_id = self.websites_by_url_path[f"courses/{site_name}"].uuid
        except KeyError:
            # This point will probably never be reached, but we'll keep it here
            # to support any links that might mistakenly use `name` instead
            # of `url_path`.
            site_id = self.websites[site_name]

        return self.find_within_site(site_id, relative_path)

    def find_within_site(self, website_id, site_relative_path: str) -> WebsiteContent:
        """Lookup content by its website_id and content-relative URL.

        Example:
        =======
        content_lookup = ContentLookup()
        content_lookup.find('some-uuid', '/pages/assignments/hw1')
        """
        if site_relative_path == "/":
            return self.metadata[website_id]

        site_relative_path = site_relative_path.rstrip("/")

        try:
            content_relative_dirpath, content_filename = os.path.split(
                site_relative_path
            )
            dirpath = self.standardize_dirpath(content_relative_dirpath)
            filename = self.standardize_filename(content_filename)
            return self.website_contents[(website_id, dirpath, filename)]
        except KeyError:
            dirpath = self.standardize_dirpath(site_relative_path)
            filename = "_index"
            return self.website_contents[(website_id, dirpath, filename)]


class UrlSiteRelativiser:
    """
    Given a possibly-legacy, root-relative url returns a tuple (site,
    course_relative_url).

    Example 1:
        /courses/architecture/4-601-introduction-to-art-history-fall-2018/assignments/4.601-second-paper
        becomes:
        "/assignments/4.601-second-paper"

    Example 2:
        "/courses/18-02sc-multivariable-calculus-fall-2010"
        becomes
        "/"

    Example 3:
        "/resources/res-21g-01-kana-spring-2010/katakana"
        becomes
        "/katakana"
    """

    def __init__(self):
        websites = Website.objects.all()
        self.website_lookup = {w.name: w for w in websites}

    def __call__(self, url: str):
        parsed = urlparse(url)
        path = parsed.path
        pieces = path.split("/")
        try:
            site_index, site_name = next(
                (i, name)
                for i, name in enumerate(pieces)
                if name in self.website_lookup
            )
        except StopIteration as err:
            msg = f"'{url} does not contain a website name."
            raise ValueError(msg) from err
        site_relative_path = "/" + "/".join(pieces[site_index + 1 :])

        site_relative_url = site_relative_path
        if parsed.fragment:
            site_relative_url += f"#{parsed.fragment}"
        return self.website_lookup[site_name], site_relative_url


class LegacyFileLookup:
    """
    Find content by legacy filename.

    Example: In site "21h-104j...", find:
        MIT21H_104JF10_syllf09.pdf
    Matches:
        WebsiteContent(
            file="/courses/21h-104j-riots-strikes-and-conspiracies-in-american-history-fall-2010/95e03c4c924a62a8e3876d49f51889c0_MIT21H_104JF10_syllf09.pdf",
            website=Website(name="21h-104j-riots-strikes-and-conspiracies-in-american-history-fall-2010"),
            # NOT used for matching!
            filename="mit21h_104jf10_syllf09",
            dirpath="content/resources",
        )

    NOTE:
    """  # noqa: D414

    class MultipleMatchError(Exception):
        pass

    def __init__(self):
        website_contents = WebsiteContent.all_objects.all().prefetch_related(
            "website", "parent"
        )
        contents_by_file = defaultdict(list)
        for wc in website_contents:
            if wc.file:
                legacy_filename = self.extract_legacy_filename_from_file(wc.file.name)
                if legacy_filename is None:
                    continue
                key = (wc.website_id, legacy_filename)
                # The pair (website_id, original_filename) is probably unique,
                # but let's key a list just in case it's not.
                contents_by_file[key].append(wc)
        self.contents_by_file = dict(contents_by_file)

    @staticmethod
    def extract_legacy_filename_from_file(file: str):
        """
        Infer legacy ocw filename from WebsiteContent.file.

        Example:
        ========
        /courses/8-02-physics-ii-electricity-and-magnetism-spring-2007/96731f9e4d806330f389243c5acda5c3_27bridge3dthumb.jpg
        becomes:
        27bridge3dthumb.jpg

        This is useful when matching OCW-legacy URLs to OCW-next resources because
        WebsiteContent.file has the original filename, whereas WebsiteContent.filename
        has various replacements (e.g., capitalization removed, often no extension,
        periods replaced by dashes).
        """
        _, filename = os.path.split(file)
        try:
            UUID(filename[:32])
            return filename[32:].lstrip("_")
        except ValueError:
            return None

    def find(self, website_id: str, legacy_site_rel_path: str):
        """
        Find content by legacy site-relative URL plus site id.

        Args:
        ====
            - website_id: uuid of site in which content should exist
            - legacy_site_rel_path: legacy site relative path, i.e., the portion
                of the legacy url after the site name.

        The match between legacy_site_rel_path and content objects is
        performed primarily based on the `file` property. We use `file` NOT
        dirpath + filename because
            - filename has generally be lowercased, and the legacy URLs are
                case-sensitive.
            - filename does not include the file extension, which is often
                necessary to uniquely identify a match.

        Duplicate filenames
        ===================
        One complication is duplicate legacy filenames. Consider the following
        legacy URLs:

            /courses/civil-and-environmental-engineering/1-017-computing-and-data-analysis-for-environmental-applications-fall-2003/lecture-notes/cdffit.m
            /courses/civil-and-environmental-engineering/1-017-computing-and-data-analysis-for-environmental-applications-fall-2003/assignments/cdffit.m

        The corresponding `legacy_site_rel_path`s are:
            /lecture-notes/cdffit.m
            /assignments/cdffit.m

        The corresponding OCW-Next content objects have:
            file                    filename        dirpath
            .../uuid1_cdffit.m      cdffit-1        content/resources
            .../uuid2_cdffit.m      cdffit          content/resources

        Looking only at these two content objects, we can't decide which one
        goes with `/assignments/cdffit.m` vs `/lecture-notes/cdffit.m`.(The
        beginning portion of `file` contains no useful information.)

        To decide which content goes with which legacy_site_rel_path, we need
        to look at the parent objects, too:

        The corresponding OCW-Next content objects have:
            file                    filename        dirpath             parent_filename  parent_dirpath
            .../uuid1_cdffit.m      cdffit-1        content/resources   assignments      content/pages
            .../uuid2_cdffit.m      cdffit          content/resources   lecture-notes    content/pages
        """  # noqa: E501
        url_dirpath, legacy_filename = os.path.split(legacy_site_rel_path)
        key = (website_id, legacy_filename)
        matches = self.contents_by_file[key]
        if len(matches) == 1:
            return matches[0]

        def parent_matches_url(wc):
            if wc.parent is None:
                return False
            return url_dirpath in wc.parent.dirpath + "/" + wc.parent.filename

        refined = [m for m in matches if parent_matches_url(m)]
        if len(refined) == 1:
            return refined[0]
        msg = f"Found {len(refined)} after inspecting parents."
        raise self.MultipleMatchError(msg)
