import pytest

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rules.gallery_image_rename import (
    GalleryImageRenameRule,
)

pytestmark = pytest.mark.django_db

UUID_PREFIX = "ab3d029952cda060f4afcd811189a591"  # pragma: allowlist secret


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""  # noqa: D401
    rule = GalleryImageRenameRule()
    return WebsiteContentMarkdownCleaner(rule)


def test_replaces_href_when_rename_confirmed():
    """Href is rewritten when the stripped basename exists and the UUID name does not."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}',
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert (
        gallery.markdown
        == '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    )


def test_leaves_href_unchanged_when_original_still_exists():
    """A collision-skipped rename leaves the UUID-prefixed file in place; href must not change."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    )
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_leaves_href_unchanged_when_no_matching_file_exists():
    """No sibling content confirms the rename; href is left untouched."""
    website = WebsiteFactory.create()
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_href_without_uuid_prefix_unchanged():
    """Hrefs that never had a UUID prefix are left alone."""
    website = WebsiteFactory.create()
    original_markdown = '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_ignores_other_shortcodes():
    """Non-gallery shortcodes are left untouched even if they resemble a match."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    original_markdown = f'{{{{< resource_link "{UUID_PREFIX}_photo.jpg" "text" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_preserves_other_shortcode_params():
    """Only href changes; data-ngdesc/text params are preserved verbatim."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=(
            f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" '
            'data-ngdesc="A rock sample" text="caption text" >}}'
        ),
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == (
        '{{< image-gallery-item href="photo.jpg" '
        'data-ngdesc="A rock sample" text="caption text" >}}'
    )


def test_only_matches_within_same_website():
    """A rename confirmed in one website must not affect galleries in another."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    # The renamed file lives in website_b, not website_a.
    WebsiteContentFactory.create(
        website=website_b, file=f"sites/{website_b.name}/photo.jpg"
    )
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(
        website=website_a, markdown=original_markdown
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown
