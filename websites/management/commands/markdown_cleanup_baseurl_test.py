"""Tests for convert_baseurl_links_to_resource_links.py"""
import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleanup_baseurl import (
    BaseurlReplacer,
    ContentLookup,
    WebsiteContentMarkdownCleaner,
)


def get_markdown_cleaner(website_contents):
    """Convenience to get baseurl-replacing markdown cleaner"""
    content_lookup = ContentLookup(website_contents)
    replacer = BaseurlReplacer(content_lookup)
    return WebsiteContentMarkdownCleaner(BaseurlReplacer.baseurl_regex, replacer)


@pytest.mark.parametrize(
    "markdown, expected_markdown",
    [
        (
            # standard link on same line as baseurl link
            R"Cats are on [wikipedia](https://en.wikipedia.org/wiki/Cat). I also have a cat [meow]({{< baseurl >}}/resources/path/to/file1).",
            R'Cats are on [wikipedia](https://en.wikipedia.org/wiki/Cat). I also have a cat {{< resource_link content-uuid-1 "meow" >}}.',
        ),
        (
            R'This is a link with quote in title: [Cats say "meow"]({{< baseurl >}}/resources/path/to/file1).',
            R'This is a link with quote in title: {{< resource_link content-uuid-1 "Cats say \"meow\"" >}}.',
        ),
        (
            R"This link should change [text title]({{< baseurl >}}/resources/path/to/file1) cool",
            R'This link should change {{< resource_link content-uuid-1 "text title" >}} cool',
        ),
        (
            # < resource_link > short code is only for textual titles
            "This link should not change: [![image](cat.com)]({{< baseurl >}}/resources/path/to/file1) for now",
            "This link should not change: [![image](cat.com)]({{< baseurl >}}/resources/path/to/file1) for now",
        ),
        (
            # Titles with nested brackets may not be feasible with a regex approach, but they're very rare anyway.
            "This link should not change: [title has [square] braackets]({{< baseurl >}}/resources/path/to/file1) for now",
            "This link should not change: [title has [square] braackets]({{< baseurl >}}/resources/path/to/file1) for now",
        ),
        (
            "This link should not change: [title \n has newline]({{< baseurl >}}/resources/path/to/file1) for now",
            "This link should not change: [title \n has newline]({{< baseurl >}}/resources/path/to/file1) for now",
        ),
    ],
)
def test_baseurl_replacer_specific_replacements(markdown, expected_markdown):
    """Test specific replacements"""
    website_uuid = "website-uuid"
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )

    linkables = [
        WebsiteContentFactory.build(
            website_id=website_uuid,
            dirpath="content/resources/path/to",
            filename=f"file{x}",
            text_id=f"content-uuid-{x}",
        )
        for x in range(3)
    ]

    cleaner = get_markdown_cleaner(linkables)
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown


def test_baseurl_replacer_replaces_baseurl_links():
    """replace_baseurl_links should replace multiple links with expected values"""

    markdown = R"""
    « [Previous]({{< baseurl >}}/pages/reducing-problem) | [Next]({{< baseurl >}}/pages/vibration-analysis) »

    ### Lecture Videos

    *   Watch [Lecture 21: Vibration Isolation]({{< baseurl >}}/resources/lecture-21)
        *   Video Chapters
            *   [Demonstration of a vibration isolation system-strobe light and vibrating beam]({{< baseurl >}}/resources/demos/vibration-isolation)
            * Euler's formula

    Wasn't [the video]({{< baseurl >}}/resources/lecture-21) fun? Yes it was!
    """

    expected = R"""
    « {{< resource_link uuid-111 "Previous" >}} | {{< resource_link uuid-222 "Next" >}} »

    ### Lecture Videos

    *   Watch {{< resource_link uuid-333 "Lecture 21: Vibration Isolation" >}}
        *   Video Chapters
            *   {{< resource_link uuid-444 "Demonstration of a vibration isolation system-strobe light and vibrating beam" >}}
            * Euler's formula

    Wasn't {{< resource_link uuid-333 "the video" >}} fun? Yes it was!
    """

    website = WebsiteFactory.build()
    target_content = WebsiteContentFactory.build(markdown=markdown, website=website)

    linked_contents = [
        WebsiteContentFactory.build(website=website, **kwargs)
        for kwargs in [
            {
                "dirpath": "content/pages",
                "filename": "reducing-problem",
                "text_id": "uuid-111",
            },
            {
                "dirpath": "content/pages",
                "filename": "vibration-analysis",
                "text_id": "uuid-222",
            },
            {
                "dirpath": "content/resources",
                "filename": "lecture-21",
                "text_id": "uuid-333",
            },
            {
                "dirpath": "content/resources/demos",
                "filename": "vibration-isolation",
                "text_id": "uuid-444",
            },
        ]
    ]

    cleaner = get_markdown_cleaner(linked_contents)
    cleaner.update_website_content_markdown(target_content)
    assert target_content.markdown == expected


@pytest.mark.parametrize(
    "website_uuid, should_markdown_change",
    [("website-uuid-111", True), ("website-uuid-222", False)],
)
def test_baseurl_replacer_replaces_content_in_same_course(
    website_uuid, should_markdown_change
):
    """
    Double check that if the dirpath + filename match multiple times, the
    content chosen is from the same course as the markdown being edited
    """

    markdown = R"""
    Kittens [meow]({{< baseurl >}}/resources/pets/cat) meow.
    """

    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id="website-uuid-111"
    )

    linkable = WebsiteContentFactory.build(
        website_id=website_uuid,
        dirpath="content/resources/pets",
        filename="cat",
        text_id="uuid-111",
    )

    cleaner = get_markdown_cleaner([linkable])
    cleaner.update_website_content_markdown(target_content)

    is_markdown_changed = target_content.markdown != markdown
    assert is_markdown_changed == should_markdown_change
