"""Tests for convert_baseurl_links_to_resource_links.py"""
from unittest.mock import Mock, patch

import pytest

from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.baseurl_rule import (
    CONTENT_FILENAME_MAX_LEN,
    BaseurlReplacementRule,
)
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)


def get_markdown_cleaner(website_contents):
    """Convenience to get rule-specific cleaner"""
    with patch(
        "websites.management.commands.markdown_cleaning.baseurl_rule.get_all_website_content"
    ) as mock:
        mock.return_value = website_contents
        rule = BaseurlReplacementRule()
        return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ["markdown", "expected_markdown"],
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
        (  # Ignores backslashes around the title brackets
            R'This is a link with quote in title: \[Cats say "meow"\]({{< baseurl >}}/resources/path/to/file1).',
            R'This is a link with quote in title: {{< resource_link content-uuid-1 "Cats say \"meow\"" >}}.',
        ),
        (
            R"This link should change [text title]({{< baseurl >}}/resources/path/to/file1) cool",
            R'This link should change {{< resource_link content-uuid-1 "text title" >}} cool',
        ),
        (
            R"This link includes a fragment [text title]({{< baseurl >}}/resources/path/to/file1#some-fragment) cool",
            R'This link includes a fragment {{< resource_link content-uuid-1 "text title" "#some-fragment" >}} cool',
        ),
        (
            R"This link includes a fragment with slash first [text title]({{< baseurl >}}/resources/path/to/file1/#some-fragment) cool",
            R'This link includes a fragment with slash first {{< resource_link content-uuid-1 "text title" "#some-fragment" >}} cool',
        ),
        (
            # < resource_link > short code is only for textual titles
            "This link should not change: [![image](cat.com)]({{< baseurl >}}/resources/path/to/file1) for now",
            "This link should not change: [![image](cat.com)]({{< baseurl >}}/resources/path/to/file1) for now",
        ),
        (
            # < resource_link > short code is only for textual titles
            R"This should not change [{{< resource uuid1 >}}]({{< baseurl >}}/resources/mit18_02sc_l20brds_5)",
            R"This should not change [{{< resource uuid1 >}}]({{< baseurl >}}/resources/mit18_02sc_l20brds_5)",
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
def test_baseurl_replacer_specific_title_replacements(markdown, expected_markdown):
    """Test specific replacements"""
    website_uuid = "website-uuid"
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )
    ContentSyncStateFactory.build(content=target_content)

    linkable = WebsiteContentFactory.build(
        website_id=website_uuid,
        dirpath="content/resources/path/to",
        filename="file1",
        text_id="content-uuid-1",
    )

    cleaner = get_markdown_cleaner([linkable])
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown


@pytest.mark.parametrize(
    ["url", "content_relative_dirpath", "filename"],
    [
        (
            # url is to an index file, not to dirpath/filename
            "/pages/pets",
            "/pages/pets",
            "_index",
        ),
        ("/pages/pets/c.a.t", "/pages/pets", "c-a-t"),
        (
            "/pages/pets/" + "z" * CONTENT_FILENAME_MAX_LEN + "meowmeow",
            "/pages/pets",
            "z" * CONTENT_FILENAME_MAX_LEN,
        ),
    ],
)
def test_baseurl_replacer_handle_specific_url_replacements(
    url, content_relative_dirpath, filename
):
    """Test specific replacements"""
    website_uuid = "website-uuid"
    markdown = f"my [pets]({{{{< baseurl >}}}}{url}) are legion"
    expected_markdown = 'my {{< resource_link content-uuid "pets" >}} are legion'
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )
    target_sync_state = ContentSyncStateFactory.build(content=target_content)

    linkable = WebsiteContentFactory.build(
        website_id=website_uuid,
        dirpath=f"content{content_relative_dirpath}",
        filename=filename,
        text_id="content-uuid",
    )

    cleaner = get_markdown_cleaner([linkable])
    cleaner.update_website_content_markdown(target_content)

    assert target_content.markdown == expected_markdown
    assert target_sync_state.current_checksum == target_content.calculate_checksum()


def test_baseurl_replacer_handles_index_files():
    """Test specific replacements"""
    website_uuid = "website-uuid"
    markdown = R"my [pets]({{< baseurl >}}/pages/cute/pets) are legion"
    expected_markdown = R'my {{< resource_link content-uuid "pets" >}} are legion'
    target_content = WebsiteContentFactory.build(
        markdown=markdown, website_id=website_uuid
    )
    target_sync_state = ContentSyncStateFactory.build(content=target_content)

    linkable = WebsiteContentFactory.build(
        website_id=website_uuid,
        dirpath="content/pages/cute/pets",
        filename="_index",
        text_id="content-uuid",
    )

    cleaner = get_markdown_cleaner([linkable])
    cleaner.update_website_content_markdown(target_content)

    assert linkable.filename not in target_content.markdown
    assert target_content.markdown == expected_markdown
    assert target_sync_state.current_checksum == target_content.calculate_checksum()


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
    target_sync_state = ContentSyncStateFactory.build(content=target_content)

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
    assert target_sync_state.current_checksum == target_content.calculate_checksum()


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
    ContentSyncStateFactory.build(content=target_content)

    linkable = WebsiteContentFactory.build(
        website_id=website_uuid,
        dirpath="content/resources/pets",
        filename="cat",
        text_id="uuid-111",
    )

    cleaner = get_markdown_cleaner([linkable])
    cleaner.update_website_content_markdown(target_content)

    is_markdown_changed = target_content.markdown != markdown
    is_checksum_changed = (
        target_content.content_sync_state.current_checksum
        == target_content.calculate_checksum()
    )
    assert is_markdown_changed == should_markdown_change
    # assert is_checksum_changed == should_markdown_change
