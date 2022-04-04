from uuid import uuid4

import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rootrelative_urls import (
    RootRelativeUrlRule,
)
from websites.management.commands.markdown_cleaning.testing_utils import (
    allow_invalid_shortcode_uuids,
    patch_website_all,
    patch_website_contents_all,
)


def string_uuid():
    return str(uuid4()).replace("-", "")


def get_markdown_cleaner(websites, website_contents):
    """Convenience to get rule-specific cleaner"""
    with patch_website_contents_all(website_contents):
        with patch_website_all(websites):
            rule = RootRelativeUrlRule()
            return WebsiteContentMarkdownCleaner(rule)


@pytest.mark.parametrize(
    ["site_name", "markdown", "expected_markdown"],
    [
        (
            "site_one",
            R"A link to [same course](/courses/some_dep/site_one/pages/stuff/page1) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" %}} goes to resource_link',
        ),
        # images wrapped in links should stay that way for now, but still fix outer URL
        (
            "site_one",
            R"A link to [![image](some/image)](/courses/some_dep/site_one/pages/stuff/page1) stays markdown",
            R"A link to [![image](some/image)](/courses/site_one/pages/stuff/page1) stays markdown",
        ),
        # finds correct content even though "some_department"
        (
            "site_one",
            R"A link to [same course](/courses/some_department/site_one/pages/stuff/page1) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" %}} goes to resource_link',
        ),
        (
            "site_one",
            R"A link to [same course](/courses/some_department/site_one/pages/stuff/page1#some-fragment) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" "#some-fragment" %}} goes to resource_link',
        ),
        (
            "site_two",
            "A link to [different course](/courses/site_one/pages/stuff/page1) stays root-relative",
            "A link to [different course](/courses/site_one/pages/stuff/page1) stays root-relative",
        ),
        # finds correct content even though "some_department"
        (
            "site_two",
            "A link to [different course](/courses/some_department/site_one/pages/stuff/page1) stays root-relative",
            "A link to [different course](/courses/site_one/pages/stuff/page1) stays root-relative",
        ),
        (
            "site_two",
            "A link to [different course](/courses/some_department/site_one/pages/stuff/page1#a-b) stays root-relative",
            "A link to [different course](/courses/site_one/pages/stuff/page1#a-b) stays root-relative",
        ),
    ],
)
@allow_invalid_shortcode_uuids()
def test_rootrel_rule_only_uses_resource_links_for_same_site(
    markdown, site_name, expected_markdown
):
    w1 = WebsiteFactory.build(name="site_one")
    w2 = WebsiteFactory.build(name="site_two")
    websites = {w.name: w for w in [w1, w2]}
    c1 = WebsiteContentFactory.build(
        website=w1, filename="page1", dirpath="content/pages/stuff", text_id="uuid-1"
    )

    content_to_clean = WebsiteContentFactory.build(
        website=websites[site_name], markdown=markdown
    )

    cleaner = get_markdown_cleaner([w1], [c1])
    cleaner.update_website_content(content_to_clean)

    assert content_to_clean.markdown == expected_markdown


@pytest.mark.parametrize(
    ["site_name", "markdown", "expected_markdown"],
    [
        (
            "site_one",
            R"A link to [same course](/courses/department/site_one/) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" %}} goes to resource_link',
        ),
        (  # no trailing slash in link
            "site_one",
            R"A link to [same course](/courses/department/site_one) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" %}} goes to resource_link',
        ),
        (  # no trailing slash in link
            "site_one",
            R"A link to [same course](/courses/department/site_one#a-b-c) goes to resource_link",
            R'A link to {{% resource_link "uuid-1" "same course" "#a-b-c" %}} goes to resource_link',
        ),
        (
            "site_two",
            R"A link to [different course](/courses/department/site_one/) stays root relative",
            R"A link to [different course](/courses/site_one) stays root relative",
        ),
        (  # no trailing slash on the link
            "site_two",
            R"A link to [different course](/courses/department/site_one) stays root relative",
            R"A link to [different course](/courses/site_one) stays root relative",
        ),
        (
            "site_two",
            R"A link to [different course](/courses/department/site_one#a-b-c) stays root relative",
            R"A link to [different course](/courses/site_one#a-b-c) stays root relative",
        ),
    ],
)
@allow_invalid_shortcode_uuids()
def test_rootrel_rule_handles_site_homeages_correctly(
    markdown, site_name, expected_markdown
):
    w1 = WebsiteFactory.build(name="site_one")
    w2 = WebsiteFactory.build(name="site_two")
    websites = {w.name: w for w in [w1, w2]}
    c1 = WebsiteContentFactory.build(
        website=w1, type="sitemetadata", filename="", dirpath="", text_id="uuid-1"
    )
    content_to_clean = WebsiteContentFactory.build(
        website=websites[site_name], markdown=markdown
    )

    cleaner = get_markdown_cleaner([w1], [c1])
    cleaner.update_website_content(content_to_clean)

    assert content_to_clean.markdown == expected_markdown


@pytest.mark.parametrize(
    ["site_name", "markdown", "expected_markdown"],
    [
        (
            "site_one",
            R"cool image ![alt text here](/courses/dep/site_one/blah/old_image_filename123.jpg) cool ",
            R'cool image {{< resource uuid="uuid-1" >}} cool ',
        ),
        # This should convert the inner image to resource and fix outer destination
        (
            "site_one",
            R"cool image [![alt text here](/courses/dep/site_one/blah/old_image_filename123.jpg)](/courses/dep/site_one/dir/some_page) cool ",
            R'cool image [{{< resource uuid="uuid-1" >}}](/courses/site_one/pages/dir/some_page) cool ',
        ),
        # This should convert the inner image to resource and leave outer destination alone
        (
            "site_one",
            R"cool image [![alt text here](/courses/dep/site_one/blah/old_image_filename123.jpg)](/this/dest/should/stay/same) cool ",
            R'cool image [{{< resource uuid="uuid-1" >}}](/this/dest/should/stay/same) cool ',
        ),
        (  # Do not change cross-site images. They would need the AWS file...
            "site_two",
            R"cool image ![alt text here](/courses/dep/site_one/blah/old_image_filename123.jpg) cool ",
            R"cool image ![alt text here](/courses/dep/site_one/blah/old_image_filename123.jpg) cool ",
        ),
    ],
)
@allow_invalid_shortcode_uuids()
def test_rootrel_rule_uses_images_for_image(markdown, site_name, expected_markdown):
    w1 = WebsiteFactory.build(name="site_one")
    w2 = WebsiteFactory.build(name="site_two")
    websites = {w.name: w for w in [w1, w2]}
    c1 = WebsiteContentFactory.build(
        website=w1,
        text_id="uuid-1",
        file=f"only/last/part/matters/for/now/{string_uuid()}_old_image_filename123.jpg",
        # in general the new filename is the same as old,
        # possibly appended with "-1" or "-2" if there were duplicates
        filename="new_image_filename123.jpg",
        dirpath="content/resources",
    )
    c2 = WebsiteContentFactory.build(
        website=w1,
        text_id="uuid-2",
        # in general the new filename is the same as old,
        # possibly appended with "-1" or "-2" if there were duplicates
        filename="some_page",
        dirpath="content/pages/dir",
    )
    content_to_clean = WebsiteContentFactory.build(
        website=websites[site_name], markdown=markdown
    )
    cleaner = get_markdown_cleaner([w1], [c1, c2])
    cleaner.update_website_content(content_to_clean)
    assert content_to_clean.markdown == expected_markdown
