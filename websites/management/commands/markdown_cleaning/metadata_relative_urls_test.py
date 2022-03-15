from content_sync.factories import ContentSyncStateFactory
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.metadata_relative_urls import (
    MetadataRelativeUrlsFix,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    patch_website_contents_all,
)


def get_markdown_cleaner(website_contents):
    """Convenience to get rule-specific cleaner"""
    with patch_website_contents_all(website_contents):
        rule = MetadataRelativeUrlsFix()
        return WebsiteContentMarkdownCleaner(rule)


def test_updates_multiple_metadata_fields():
    """
    Check that a single call to update_website_content modifies multiple fields
    for rules that have multiple fields associated.
    """
    assert len(MetadataRelativeUrlsFix.fields) > 1

    website = WebsiteFactory.build(name="site-1")
    wc1 = WebsiteContentFactory.build(
        filename="thing1",
        dirpath="content/resources",
        website=website,
    )
    wc2 = WebsiteContentFactory.build(
        filename="thing2", dirpath="content/pages/two", website=website
    )

    content_to_clean = WebsiteContentFactory.build(
        metadata={
            "related_resources_text": """Hello
                Change this: [to thing1](resources/thing1#fragment "And a title!") cool'
                
                Leave this alone: [wiki](https://wikipedia.org) same

                And this [course link](/courses/8-02/pages/jigawatts)
            """,
            "image_metadata": {"caption": "And now [thing2](pages/two/thing2)"},
        },
        website=website,
    )
    ContentSyncStateFactory.build(content=content_to_clean)

    cleaner = get_markdown_cleaner([wc1, wc2])
    cleaner.update_website_content(content_to_clean)

    expected_related_resources = """Hello
                Change this: [to thing1](/courses/site-1/resources/thing1#fragment) cool'
                
                Leave this alone: [wiki](https://wikipedia.org) same

                And this [course link](/courses/8-02/pages/jigawatts)
            """
    expected_caption = "And now [thing2](/courses/site-1/pages/two/thing2)"
    assert (
        content_to_clean.metadata["related_resources_text"]
        == expected_related_resources
    )
    assert content_to_clean.metadata["image_metadata"]["caption"] == expected_caption
