import pytest
from botocore.exceptions import ClientError

from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.management.commands.markdown_cleaning.cleaner import (
    WebsiteContentMarkdownCleaner,
)
from websites.management.commands.markdown_cleaning.rules.gallery_image_rename import (
    GalleryImageRenameRule,
)

pytestmark = pytest.mark.django_db

# A resource's legacy filename prefix is its text_id with the dashes removed,
# which is what image_gallery_item_uuid records in the item's uuid param.
IMAGE_UUID = "ab3d0299-52cd-a060-f4af-cd811189a591"  # pragma: allowlist secret
UUID_PREFIX = IMAGE_UUID.replace("-", "")


@pytest.fixture
def mock_s3(mocker):
    """Mock the S3 client used to confirm a renamed object really exists."""
    return mocker.patch(
        "websites.management.commands.markdown_cleaning.rules"
        ".gallery_image_rename.get_boto3_client"
    )


def missing_key_error():
    """Build a head_object ClientError for a key that is not in the bucket."""
    return ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")


def get_markdown_cleaner():
    """Convenience to get rule-specific markdown cleaner"""  # noqa: D401
    rule = GalleryImageRenameRule()
    return WebsiteContentMarkdownCleaner(rule)


def test_replaces_href_when_rename_confirmed(mock_s3):
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


def test_leaves_href_unchanged_when_original_still_exists(mock_s3):
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


def test_leaves_href_unchanged_when_no_matching_file_exists(mock_s3):
    """No sibling content confirms the rename; href is left untouched."""
    website = WebsiteFactory.create()
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_href_without_uuid_prefix_unchanged(mock_s3):
    """Hrefs that never had a UUID prefix are left alone."""
    website = WebsiteFactory.create()
    original_markdown = '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_ignores_other_shortcodes(mock_s3):
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


def test_preserves_other_shortcode_params(mock_s3):
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


def test_only_matches_within_same_website(mock_s3):
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


def test_leaves_href_unchanged_when_s3_object_missing(mock_s3):
    """DB says the rename happened but the object is not in S3 -- do not rewrite.

    Guards against DB/S3 drift: rewriting here would point the gallery at a key
    that does not exist.
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    mock_s3.return_value.head_object.side_effect = missing_key_error()
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_leaves_href_unchanged_when_s3_check_errors(mock_s3):
    """An S3 lookup that fails for any other reason is treated as unconfirmed."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    mock_s3.return_value.head_object.side_effect = OSError("connection reset")
    original_markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery = WebsiteContentFactory.create(website=website, markdown=original_markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == original_markdown


def test_s3_check_strips_leading_slash_from_key(settings, mock_s3):
    """Legacy /courses/... file values are normalized before the S3 lookup."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"/courses/{website.name}/photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}',
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    mock_s3.return_value.head_object.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=f"courses/{website.name}/photo.jpg",
    )
    assert (
        gallery.markdown
        == '{{< image-gallery-item href="photo.jpg" text="a caption" >}}'
    )


def test_s3_existence_check_is_cached_across_pages(mock_s3):
    """The same renamed object is only looked up in S3 once per run."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    markdown = f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}'
    gallery_one = WebsiteContentFactory.create(website=website, markdown=markdown)
    gallery_two = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery_one)
    cleaner.update_website_content(gallery_two)

    assert mock_s3.return_value.head_object.call_count == 1


def test_no_s3_lookup_when_db_check_already_fails(mock_s3):
    """A collision-skipped file is ruled out from the DB alone, with no S3 call."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="a caption" >}}}}',
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    mock_s3.return_value.head_object.assert_not_called()


def gallery_item(uuid=IMAGE_UUID, href=f"{UUID_PREFIX}_photo.jpg"):
    """Build an image-gallery-item shortcode, uuid first as the uuid rule emits it."""
    params = []
    if uuid is not None:
        params.append(f'uuid="{uuid}"')
    params.append(f'href="{href}"')
    return "{{< image-gallery-item " + " ".join(params) + ' text="a caption" >}}'


def test_uuid_param_resolves_target_that_basename_matching_would_miss(mock_s3):
    """The uuid param names the resource directly, so the current filename is authoritative.

    Stripping the prefix off the href would look for photo.jpg, which is not
    what the resource is called any more.
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        text_id=IMAGE_UUID,
        file=f"sites/{website.name}/renamed-photo.jpg",
    )
    gallery = WebsiteContentFactory.create(website=website, markdown=gallery_item())

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == (
        f'{{{{< image-gallery-item uuid="{IMAGE_UUID}" '
        'href="renamed-photo.jpg" text="a caption" >}}'
    )


def test_uuid_resolution_leaves_collision_skipped_file_alone(mock_s3):
    """A file whose rename was skipped still carries its prefix, so the href already matches."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        text_id=IMAGE_UUID,
        file=f"sites/{website.name}/{UUID_PREFIX}_photo.jpg",
    )
    markdown = gallery_item()
    gallery = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == markdown


def test_uuid_resolution_still_confirms_s3(mock_s3):
    """A uuid-resolved target is verified in S3 like any other."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, text_id=IMAGE_UUID, file=f"sites/{website.name}/photo.jpg"
    )
    mock_s3.return_value.head_object.side_effect = missing_key_error()
    markdown = gallery_item()
    gallery = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == markdown


def test_falls_back_to_basename_when_uuid_matches_nothing(mock_s3):
    """A uuid that no longer names a resource falls back to the basename check."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=gallery_item(uuid="99999999-9999-4999-8999-999999999999"),
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == (
        '{{< image-gallery-item uuid="99999999-9999-4999-8999-999999999999" '
        'href="photo.jpg" text="a caption" >}}'
    )


def test_uuid_is_scoped_to_the_same_website(mock_s3):
    """text_id is unique per website, so a match in another site is not the target."""
    website_a = WebsiteFactory.create()
    website_b = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website_b,
        text_id=IMAGE_UUID,
        file=f"sites/{website_b.name}/renamed-photo.jpg",
    )
    markdown = gallery_item()
    gallery = WebsiteContentFactory.create(website=website_a, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == markdown


def test_uuid_resolution_preserves_a_path_valued_href(mock_s3):
    """image_gallery_item_uuid accepts a path-valued href, so the path must survive."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        text_id=IMAGE_UUID,
        file=f"sites/{website.name}/photo.jpg",
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=gallery_item(href=f"/courses/{website.name}/{UUID_PREFIX}_photo.jpg"),
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == (
        f'{{{{< image-gallery-item uuid="{IMAGE_UUID}" '
        f'href="/courses/{website.name}/photo.jpg" text="a caption" >}}}}'
    )


def test_uuid_resolution_leaves_correct_path_valued_href_alone(mock_s3):
    """An already-correct path-valued href must not be flattened to its basename."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, text_id=IMAGE_UUID, file=f"sites/{website.name}/photo.jpg"
    )
    markdown = gallery_item(href=f"/courses/{website.name}/photo.jpg")
    gallery = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == markdown


def test_basename_fallback_preserves_a_path_valued_href(mock_s3):
    """Without a uuid param a path-valued href is still repaired, path intact."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    gallery = WebsiteContentFactory.create(
        website=website,
        markdown=gallery_item(
            uuid=None, href=f"/courses/{website.name}/{UUID_PREFIX}_photo.jpg"
        ),
    )

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == (
        f'{{{{< image-gallery-item href="/courses/{website.name}/photo.jpg" '
        'text="a caption" >}}'
    )


def test_uuid_resolution_is_cached_across_pages(mock_s3, django_assert_num_queries):
    """A resource referenced by many pages is looked up once, not once per page."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website,
        text_id=IMAGE_UUID,
        file=f"sites/{website.name}/renamed-photo.jpg",
    )
    first = WebsiteContentFactory.create(website=website, markdown=gallery_item())
    second = WebsiteContentFactory.create(website=website, markdown=gallery_item())

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(first)
    with django_assert_num_queries(0):
        cleaner.update_website_content(second)

    assert 'href="renamed-photo.jpg"' in second.markdown


def test_item_without_href_is_left_alone(mock_s3):
    """An item carrying no href must not take down the page it sits on."""
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    markdown = (
        '{{< image-gallery-item data-ngdesc="no href here" text="a caption" >}}\n'
        f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" text="fine" >}}}}'
    )
    gallery = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    # The href-less item is untouched and the valid one beside it is still fixed.
    assert '{{< image-gallery-item data-ngdesc="no href here" text="a caption" >}}' in (
        gallery.markdown
    )
    assert 'href="photo.jpg"' in gallery.markdown


def test_item_that_does_not_round_trip_is_left_alone(mock_s3):
    """A value the parser cannot reproduce must not be rewritten alongside the href.

    A newline inside a param tokenises apart, so re-emitting the tag would
    mangle the description. Declining is the only safe outcome.
    """
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        website=website, file=f"sites/{website.name}/photo.jpg"
    )
    markdown = (
        f'{{{{< image-gallery-item href="{UUID_PREFIX}_photo.jpg" '
        'data-ngdesc="line one\nline two" text="a caption" >}}'
    )
    gallery = WebsiteContentFactory.create(website=website, markdown=markdown)

    cleaner = get_markdown_cleaner()
    cleaner.update_website_content(gallery)

    assert gallery.markdown == markdown
