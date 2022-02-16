import csv
import re
from collections import namedtuple
from typing import Callable, Iterable, Match

from websites.models import WebsiteContent


def progress_bar(
    iterable: Iterable,
    prefix="",
    suffix="",
    decimals=1,
    char_length=100,
    fill="█",
    printEnd="\r",
):
    """Call in a loop to create a terminal progress bar.

    Args:
        iterable (iterable): must implement __len__
        prefix   (str): prefix string
        suffix   (str): suffix string
        decimals (int): positive number of decimals in percent complete
        length   (int): character length of bar
        fill     (str): bar fill character
        printEnd (str): end character (e.g. "\r", "\r\n")

    Yields:
        The same items as `iterable`

    From https://stackoverflow.com/a/34325723/2747370
    """
    total = len(iterable)
    # Progress Bar Printing Function

    def print_progress_bar(iteration):
        percent = ("{0:." + str(decimals) + "f}").format(
            100 * (iteration / float(total))
        )
        filledLength = int(char_length * iteration // total)
        progress = fill * filledLength + "-" * (char_length - filledLength)
        print(f"\r{prefix} |{progress}| {percent}% {suffix}", end=printEnd)

    # Initial Call
    print_progress_bar(0)
    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item
        print_progress_bar(i + 1)
    # Print New Line on Complete
    print()


class WebsiteContentMarkdownCleaner:
    """Facilitates regex-based replacements on WebsiteContent markdown.

    Args:
        pattern (str)       : The pattern to match for when making replacements.
            If the pattern uses named capturing groups, these groups will be
            included as csv columns by `write_to_csv()` method.
        replacer (callable) : A function called for every non-overlapping match
            of `pattern` and returning the replacement string. This is similar
            to the `repl` argument of `re.sub`, but is invoked with two
            arguments: `(match, website_content)`, where `website_content` is
            `website_content` object whose markdown is currently being edited.

    Note: Internally records all matches and replacement results for subsequent
    writing to csv
    """

    ReplacementMatch = namedtuple(
        "ReplacementMatch",
        ["match", "replacement", "website_content_uuid", "website_uuid"],
    )
    csv_metadata_fieldnames = [
        "original_text",
        "replacement",
        "website_content_uuid",
        "website_uuid",
    ]

    def __init__(self, pattern: str, replacer: Callable[[Match, WebsiteContent], str]):
        self.regex = self.compile_regex(pattern)

        self.text_changes: "list[WebsiteContentMarkdownCleaner.ReplacementMatch]" = []
        self.updated_website_contents: "list[WebsiteContent]" = []

        def _replacer(match: Match, website_content: WebsiteContent):
            replacement = replacer(match, website_content)
            self.text_changes.append(
                self.ReplacementMatch(
                    match,
                    replacement,
                    website_content.text_id,
                    website_content.website_id,
                )
            )
            return replacement

        self.replacer = _replacer

    def update_website_content_markdown(self, website_content: WebsiteContent):
        """
        Updates website_content's markdown in-place. Does not commit to
        database.
        """
        if not website_content.markdown:
            return

        new_markdown = self.regex.sub(
            lambda match: self.replacer(match, website_content),
            website_content.markdown,
        )
        if new_markdown != website_content.markdown:
            website_content.markdown = new_markdown
            self.updated_website_contents.append(website_content)

    @classmethod
    def compile_regex(cls, pattern):
        """Compile `pattern` and validate that it has no named capturing groups
        whose name would conflict with csv metadata fieldnames."""
        compiled = re.compile(pattern)
        for groupname in cls.csv_metadata_fieldnames:
            if groupname in compiled.groupindex:
                raise ValueError(
                    f"Regex group name {groupname} is reserved for use by {cls.__name__}"
                )
        return compiled

    def write_matches_to_csv(self, path: str):
        """Write matches and replacements to csv."""

        fieldnames = self.text_changes[0].match
        with open(path, "w", newline="") as csvfile:
            fieldnames = [*self.csv_metadata_fieldnames, *self.regex.groupindex]
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for change in self.text_changes:
                row = {
                    "website_content_uuid": change.website_content_uuid,
                    "website_uuid": change.website_uuid,
                    "original_text": change.match[0],
                    "replacement": change.replacement,
                    **change.match.groupdict(),
                }
                writer.writerow(row)
