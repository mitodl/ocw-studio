from unittest.mock import patch

import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.link_wrapped_images import (
    LinkWrappedImagesRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    allow_invalid_uuids,
    patch_website_contents_all,
)


def get_markdown_cleaner(website_contents):
    """Convenience to get rule-specific cleaner"""
    with patch_website_contents_all(website_contents):
        rule = LinkWrappedImagesRule()
        return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ["old_markdown", "new_markdown", "same_site"],
    [
        (
            """Hello [{{< resource some_uuid >}}]({{< baseurl >}}/pages/animals/unicorn) World""",
            """Hello {{< resource uuid="some_uuid" href_uuid="unicorn_uuid" >}} World""",
            True,
        ),
        (
            """Hello [{{< resource some_uuid >}}](/courses/pets/pages/animals/unicorn) World""",
            """Hello {{< resource uuid="some_uuid" href_uuid="unicorn_uuid" >}} World""",
            True,
        ),
        (
            """Hello [{{< resource some_uuid >}}](/courses/pets/pages/animals/unicorn) World""",
            """Hello {{< resource uuid="some_uuid" href="/courses/pets/pages/animals/unicorn" >}} World""",
            False,
        ),
        (
            """Hello [{{< resource some_uuid >}}](https://mit.edu) World""",
            """Hello {{< resource uuid="some_uuid" href="https://mit.edu" >}} World""",
            True,
        ),
        (
            """Hello [{{< resource some_uuid >}}](https://mit.edu) World""",
            """Hello {{< resource uuid="some_uuid" href="https://mit.edu" >}} World""",
            False,
        ),
        # Now with annoying extra text
        (
            """Hello [{{< resource some_uuid >}}Annoying extra text]({{< baseurl >}}/pages/animals/unicorn) World""",
            """Hello {{< resource uuid="some_uuid" href_uuid="unicorn_uuid" >}}{{% resource_link "unicorn_uuid" "Annoying extra text" %}} World""",
            True,
        ),
        (
            """Hello [{{< resource some_uuid >}}Annoying extra text](https://mit.edu) World""",
            """Hello {{< resource uuid="some_uuid" href="https://mit.edu" >}}[Annoying extra text](https://mit.edu) World""",
            False,
        ),
    ],
)
@allow_invalid_uuids()
def test_link_wrapped_image_replacement(old_markdown, new_markdown, same_site):
    """
    Test link-wrapped images update to resource shortcodes correctly.
    """
    w1 = WebsiteFactory.build(name="pets")
    w2 = WebsiteFactory.build(name="other-site")
    linked_content = WebsiteContentFactory.build(
        text_id="unicorn_uuid",
        filename="unicorn",
        dirpath="content/pages/animals",
        website=w1,
    )
    target_content = WebsiteContentFactory.build(
        markdown=old_markdown, website=w1 if same_site else w2
    )

    cleaner = get_markdown_cleaner([linked_content])

    cleaner.update_website_content(target_content)

    assert target_content.markdown == new_markdown
