"""Tests for image_gallery_item_uuid.py"""

import pytest

from websites.constants import (
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE,
    RESOURCE_TYPE_DOCUMENT,
    RESOURCE_TYPE_IMAGE,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner as Cleaner,
)
from websites.management.commands.markdown_cleaning.rules.image_gallery_item_uuid import (
    ImageGalleryItemUuidRule,
)

IMAGE_UUID = "c3e28341-74a4-2a89-c56c-3a1a5bcc0eff"
IMAGE_HEX = IMAGE_UUID.replace("-", "")
HREF = f"{IMAGE_HEX}_2.Niepce.jpg"

GALLERY_OPEN = '{{< image-gallery id="g1" baseUrl="/courses/site/" >}}'
GALLERY_CLOSE = "{{</ image-gallery >}}"


def item(href=HREF, uuid=None, text="Fig 1.", ngdesc="A diagram"):
    """Build an image-gallery-item shortcode, params in real-content order."""
    params = []
    if uuid is not None:
        params.append(f'uuid="{uuid}"')
    if href is not None:
        params.append(f'href="{href}"')
    if ngdesc is not None:
        params.append(f'data-ngdesc="{ngdesc}"')
    if text is not None:
        params.append(f'text="{text}"')
    return "{{< image-gallery-item " + " ".join(params) + " >}}"


def gallery(*items):
    return "\n".join([GALLERY_OPEN, *items, GALLERY_CLOSE])


def get_cleaner():
    return Cleaner(ImageGalleryItemUuidRule())


def make_image(website, text_id=IMAGE_UUID, **kwargs):
    """Create the image resource a gallery item is supposed to point at."""
    defaults = {
        "type": CONTENT_TYPE_RESOURCE,
        "metadata": {"resourcetype": RESOURCE_TYPE_IMAGE},
    }
    return WebsiteContentFactory.create(
        website=website, text_id=text_id, **{**defaults, **kwargs}
    )


def make_page(website, markdown):
    return WebsiteContentFactory.create(
        website=website, type=CONTENT_TYPE_PAGE, markdown=markdown
    )


def run(page):
    """Run the rule over `page`, returning the gallery-item notes."""
    cleaner = get_cleaner()
    cleaner.update_website_content(page)
    return [
        match.notes
        for match in cleaner.replacement_matches
        if match.notes.is_gallery_item
    ]


def outcomes(page):
    return [notes.outcome for notes in run(page)]


@pytest.mark.django_db
def test_adds_dashed_uuid_as_first_param():
    """The uuid is inserted first and every other param survives verbatim."""
    website = WebsiteFactory.create()
    make_image(website)
    page = make_page(website, gallery(item()))

    assert outcomes(page) == ["ok"]
    assert page.markdown == gallery(item(uuid=IMAGE_UUID))


@pytest.mark.django_db
def test_resolves_href_given_as_full_path():
    website = WebsiteFactory.create()
    make_image(website)
    page = make_page(website, gallery(item(href=f"/courses/some-course/{HREF}")))

    assert outcomes(page) == ["ok"]
    assert page.markdown == gallery(
        item(href=f"/courses/some-course/{HREF}", uuid=IMAGE_UUID)
    )


@pytest.mark.django_db
def test_preserves_nested_shortcodes_in_text():
    website = WebsiteFactory.create()
    make_image(website)
    text = "Hematite: Fe{{< sub 2 >}}O{{< sub 3 >}}."
    page = make_page(website, gallery(item(text=text)))

    assert outcomes(page) == ["ok"]
    assert page.markdown == gallery(item(text=text, uuid=IMAGE_UUID))


@pytest.mark.django_db
def test_leaves_other_shortcodes_untouched():
    """Only image-gallery-item is rewritten; the container and friends are not."""
    website = WebsiteFactory.create()
    make_image(website)
    markdown = "\n".join(
        [
            '{{% resource_link "aaa" "A link" %}}',
            gallery(item()),
            "{{< /image-gallery >}}",
        ]
    )
    page = make_page(website, markdown)

    assert outcomes(page) == ["ok"]
    assert page.markdown == "\n".join(
        [
            '{{% resource_link "aaa" "A link" %}}',
            gallery(item(uuid=IMAGE_UUID)),
            "{{< /image-gallery >}}",
        ]
    )


@pytest.mark.django_db
def test_is_idempotent():
    website = WebsiteFactory.create()
    make_image(website)
    page = make_page(website, gallery(item()))

    run(page)
    once = page.markdown
    assert outcomes(page) == ["already_has_uuid"]
    assert page.markdown == once


@pytest.mark.django_db
def test_skips_item_that_already_has_a_uuid():
    website = WebsiteFactory.create()
    make_image(website)
    markdown = gallery(item(uuid="something-else"))
    page = make_page(website, markdown)

    assert outcomes(page) == ["already_has_uuid"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_item_without_href():
    website = WebsiteFactory.create()
    make_image(website)
    markdown = gallery(item(href=None))
    page = make_page(website, markdown)

    assert outcomes(page) == ["no_href"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_href_without_uuid_prefix():
    website = WebsiteFactory.create()
    make_image(website)
    markdown = gallery(item(href="example_jpg.jpg"))
    page = make_page(website, markdown)

    assert outcomes(page) == ["href_no_uuid_prefix"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_uuid_that_matches_nothing():
    website = WebsiteFactory.create()
    markdown = gallery(item())
    page = make_page(website, markdown)

    assert outcomes(page) == ["uuid_not_found"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_and_flags_cross_site_reference():
    """text_id is unique per site, so a match elsewhere is not ours to use."""
    website = WebsiteFactory.create()
    make_image(WebsiteFactory.create())
    markdown = gallery(item())
    page = make_page(website, markdown)

    assert outcomes(page) == ["cross_site"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_target_that_is_not_a_resource():
    website = WebsiteFactory.create()
    make_image(website, type=CONTENT_TYPE_PAGE, metadata={})
    markdown = gallery(item())
    page = make_page(website, markdown)

    assert outcomes(page) == ["wrong_content_type"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_resource_that_is_not_an_image():
    website = WebsiteFactory.create()
    make_image(website, metadata={"resourcetype": RESOURCE_TYPE_DOCUMENT})
    markdown = gallery(item())
    page = make_page(website, markdown)

    assert outcomes(page) == ["wrong_resourcetype"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_skips_soft_deleted_target():
    website = WebsiteFactory.create()
    make_image(website).delete()
    markdown = gallery(item())
    page = make_page(website, markdown)

    assert outcomes(page) == ["target_deleted"]
    assert page.markdown == markdown


@pytest.mark.django_db
def test_notes_carry_the_resolved_target_details():
    website = WebsiteFactory.create()
    make_image(website)
    page = make_page(website, gallery(item()))

    (notes,) = run(page)
    assert notes.href == HREF
    assert notes.uuid == IMAGE_UUID
    assert notes.resolved_type == CONTENT_TYPE_RESOURCE
    assert notes.resolved_resourcetype == RESOURCE_TYPE_IMAGE


@pytest.mark.django_db
def test_page_without_gallery_items_is_not_parsed_at_all():
    """Only 330 pages of the whole corpus have galleries; skip the rest."""
    website = WebsiteFactory.create()
    markdown = '{{% resource_link "aaa" "A link" %}}'
    page = make_page(website, markdown)

    assert ImageGalleryItemUuidRule().should_parse(markdown) is False
    assert run(page) == []
    assert page.markdown == markdown
