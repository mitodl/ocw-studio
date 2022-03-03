"""Replace baseurl-based links with resource_link shortcodes."""
import importlib
import os
from collections import defaultdict
from urllib.parse import urlparse
from uuid import UUID
from websites.models import WebsiteContent, Website

filepath_migration = importlib.import_module(
    "websites.migrations.0023_website_content_filepath"
)
CONTENT_FILENAME_MAX_LEN = filepath_migration.CONTENT_FILENAME_MAX_LEN
CONTENT_DIRPATH_MAX_LEN = filepath_migration.CONTENT_DIRPATH_MAX_LEN

def remove_prefix(string: str, prefix: str):
    if string.startswith(prefix):
        return string[len(prefix):]
    return string

class ContentLookup:
    """
    Helps find content by various properties.
    """

    def __init__(self):
        website_contents = WebsiteContent.all_objects.all()
        self.website_contents = {
            (wc.website_id, wc.dirpath, wc.filename): wc for wc in website_contents
        }
        self.metadata = {
            wc.website_id: wc for wc in website_contents if wc.type == 'sitemetadata'
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

    def find(self, website_id, course_relative_url: str):
        """Lookup content by its website_id and content-relative URL.

        Example:
        =======
        content_lookup = ContentLookup()
        content_lookup.find('some-uuid', '/pages/assignments/hw1')
        """
        if course_relative_url == '/':
            return self.metadata[website_id]
        
        course_relative_url = course_relative_url.rstrip('/')

        try:
            content_relative_dirpath, content_filename = os.path.split(
                course_relative_url
            )
            dirpath = self.standardize_dirpath(content_relative_dirpath)
            filename = self.standardize_filename(content_filename)
            return self.website_contents[(website_id, dirpath, filename)]
        except KeyError:
            dirpath = self.standardize_dirpath(course_relative_url)
            filename = "_index"
            return self.website_contents[(website_id, dirpath, filename)]

class UrlSiteRelativiser:
    """
    Given a possibly-legacy, root-relative url returns a tuple (course_name,
    course_relative_url). The returned url has no leading '/'.

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
        self.website_id_lookup = { w.name: w.uuid for w in websites }

    def __call__(self, url: str):
        path = urlparse(url).path
        pieces = path.split('/')
        try:
            website_index, website_name = next(
                (i, name) for i, name in enumerate(pieces)
                if name in self.website_id_lookup
            )
        except StopIteration as err:
            raise ValueError(f"'{url} does not contain a website name.") from err
        site_relative_url = '/' + '/'.join(pieces[website_index + 1:])
        site_uuid = self.website_id_lookup[website_name]
        return site_uuid, site_relative_url

class LegacyFileLookup:

    class MultipleMatches(Exception):
        pass

    def __init__(self):
        website_contents = WebsiteContent.all_objects.all()
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
            old_filename = filename[32:].lstrip('_')
            return old_filename
        except ValueError:
            return None;

    def find(self, website_id: str, legacy_filename: str):
        key = (website_id, legacy_filename)
        return self.contents_by_file[key]
