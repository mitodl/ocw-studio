"""API functionality for websites"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast, Length
from magic import Magic
from mitol.common.utils import max_or_none, now_in_utc
from mitol.mail.api import get_message_sender

from content_sync.constants import VERSION_DRAFT
from main.utils import NestableKeyTextTransform
from users.models import User
from videos.constants import (
    YT_MAX_LENGTH_DESCRIPTION,
    YT_MAX_LENGTH_TITLE,
    YT_THUMBNAIL_IMG,
)
from websites.constants import (
    CONTENT_FILENAME_MAX_LEN,
    PUBLISH_STATUS_ABORTED,
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_SUCCEEDED,
    PUBLISH_STATUSES_FINAL,
    RESOURCE_TYPE_VIDEO,
)
from websites.messages import (
    PreviewOrPublishFailureMessage,
    PreviewOrPublishSuccessMessage,
)
from websites.models import Website, WebsiteContent, WebsiteStarter
from websites.utils import get_dict_field, get_dict_query_field, set_dict_field


log = logging.getLogger(__name__)


def get_valid_new_filename(
    website_pk: str,
    dirpath: Optional[str],
    filename_base: str,
    exclude_text_id: Optional[str] = None,
) -> str:
    """
    Given a filename to act as a base/prefix, returns a filename that will satisfy unique constraints,
    adding/incrementing a numerical suffix as necessary.

    Examples:
        In database: WebsiteContent(filename="my-filename")...
            get_valid_new_filename("my-filename") == "my-filename2"
        In database: WebsiteContent(filename="my-filename99")...
            get_valid_new_filename("my-filename99") == "my-filename100"
    """
    website_content_qset = WebsiteContent.objects.all_with_deleted().filter(
        website_id=website_pk, dirpath=dirpath
    )
    if exclude_text_id is not None:
        website_content_qset = website_content_qset.exclude(text_id=exclude_text_id)
    filename_exists = website_content_qset.filter(filename=filename_base).exists()
    if not filename_exists:
        return filename_base
    return find_available_name(
        website_content_qset,
        filename_base,
        "filename",
        max_length=CONTENT_FILENAME_MAX_LEN,
    )


def get_valid_new_slug(slug_base: str, path: str) -> str:
    """
    Given a slug to act as a base/prefix, returns a slug that will satisfy unique constraints,
    adding/incrementing a numerical suffix as necessary.
    """
    starter_qset = WebsiteStarter.objects.exclude(path=path)
    slug_exists = starter_qset.filter(slug=slug_base).exists()
    if not slug_exists:
        return slug_base
    return find_available_name(starter_qset, slug_base, "slug", max_length=30)


def find_available_name(
    website_content_qset: QuerySet,
    initial_filename_base: str,
    fieldname: str,
    max_length: Optional[int] = CONTENT_FILENAME_MAX_LEN,
    extension: Optional[str] = None,
) -> str:
    """
    Returns a filename with the lowest possible suffix given some base filename. If the applied suffix
    makes the filename longer than the filename max length, characters are removed from the
    right of the filename to make room.

    EXAMPLES:
    initial_filename_base = "myfile"
        Existing filenames = "myfile"
        Return value = "myfile1"
    initial_filename_base = "myfile"
        Existing filenames = "myfile", "myfile1" through "myfile5"
        Return value = "myfile6"
    initial_filename_base = "abcdefghijklmnopqrstuvwxyz" (26 characters, assuming 26 character max)
        Existing filenames = "abcdefghijklmnopqrstuvwxyz"
        Return value = "abcdefghijklmnopqrstuvwxy1"  # pragma: allowlist secret
    initial_filename_base = "abcdefghijklmnopqrstuvwxy" (25 characters long, assuming 26 character max)
        Existing filenames = "abc...y", "abc...y1" through "abc...y9"
        Return value = "abcdefghijklmnopqrstuvwx10"  # pragma: allowlist secret
    """
    # Keeps track of the number of characters that must be cut from the filename to be less than
    # the filename max length when the suffix is applied.
    chars_to_truncate = 0 if len(initial_filename_base) < max_length else 1
    # Any query for suffixed filenames could come up empty. The minimum suffix will be added to
    # the filename in that case.
    current_min_suffix = 2
    if extension is None:
        extension = ""
    while chars_to_truncate < len(initial_filename_base):
        name_base = initial_filename_base[
            0 : len(initial_filename_base) - chars_to_truncate
        ]
        kwargs = {
            f"{fieldname}__regex": r"{name_base}[0-9]+{extension}".format(
                name_base=name_base, extension=extension
            )
        }
        # Find names that match the namebase and have a numerical suffix, then find the max suffix
        existing_names = website_content_qset.filter(**kwargs).values_list(
            fieldname, flat=True
        )
        if extension:
            existing_names = [os.path.splitext(name)[0] for name in existing_names]
        max_suffix = max_or_none(
            int(filename[len(name_base) :]) for filename in existing_names
        )
        if max_suffix is None:
            return f"{''.join([name_base, str(current_min_suffix)])}{extension}"
        else:
            next_suffix = max_suffix + 1
            candidate_name = "".join([name_base, str(next_suffix), extension])
            # If the next suffix adds a digit and causes the filename to exceed the character limit,
            # keep searching.
            if len(candidate_name) <= max_length:
                return candidate_name
        # At this point, we know there are no suffixes left to add to this filename base that was tried,
        # so we will need to remove characters from the end of that filename base to make room for a longer
        # suffix.
        chars_to_truncate = chars_to_truncate + 1
        available_suffix_digits = max_length - (
            len(initial_filename_base) - chars_to_truncate
        )
        # If there is space for 4 digits for the suffix, the minimum value it could be is 1000, or 10^3
        current_min_suffix = 10 ** (available_suffix_digits - 1)


def fetch_website(filter_value: str) -> Website:
    """
    Attempts to fetch a Website based on several properties
    """
    if len(filter_value) in {32, 36}:
        try:
            parsed_uuid = UUID(filter_value, version=4)
            website = Website.objects.filter(uuid=parsed_uuid).first()
            if website is not None:
                return website
        except ValueError:
            pass
    website_results = Website.objects.filter(
        Q(name__iexact=filter_value)
        | Q(title__iexact=filter_value)
        | Q(short_id__iexact=filter_value)
    ).all()
    if len(website_results) == 0:
        raise Website.DoesNotExist(
            f"Could not find a Website with a matching uuid, name, short_id, or title ('{filter_value}')"
        )
    if len(website_results) == 1:
        return website_results[0]

    sorted_results = sorted(
        website_results, key=lambda _website: 1 if _website.name == filter_value else 2
    )
    return next(sorted_results)


def is_ocw_site(website: Website) -> bool:
    """Return true if the site is an OCW site"""
    return website.starter and website.starter.slug == settings.OCW_IMPORT_STARTER_SLUG


def update_youtube_thumbnail(website_id: str, metadata: Dict, overwrite=False):
    """ Assign a youtube thumbnail url if appropriate to a website's metadata"""
    website = Website.objects.get(uuid=website_id)
    if is_ocw_site(website):
        youtube_id = get_dict_field(metadata, settings.YT_FIELD_ID)
        if youtube_id and (
            not get_dict_field(metadata, settings.YT_FIELD_THUMBNAIL) or overwrite
        ):
            set_dict_field(
                metadata,
                settings.YT_FIELD_THUMBNAIL,
                YT_THUMBNAIL_IMG.format(video_id=youtube_id),
            )


def videos_with_unassigned_youtube_ids(website: Website) -> List[WebsiteContent]:
    """Return a list of WebsiteContent objects for videos with unassigned youtube ids"""
    if not is_ocw_site(website):
        return []
    query_resource_type_field = get_dict_query_field(
        "metadata", settings.FIELD_RESOURCETYPE
    )
    query_id_field = f"metadata__{'__'.join(settings.YT_FIELD_ID.split('.'))}"
    return WebsiteContent.objects.filter(
        Q(website=website)
        & Q(**{query_resource_type_field: RESOURCE_TYPE_VIDEO})
        & (
            Q(**{f"{query_id_field}__isnull": True})
            | Q(**{f"{query_id_field}": None})
            | Q(**{query_id_field: ""})
        )
    )


def videos_with_truncatable_text(website: Website) -> List[WebsiteContent]:
    """Return a list of WebsiteContent objects with text fields that will be truncated in YouTube"""
    if not is_ocw_site(website):
        return []
    query_resource_type_field = get_dict_query_field(
        "metadata", settings.FIELD_RESOURCETYPE
    )
    yt_description_fields = settings.YT_FIELD_DESCRIPTION.split(".")
    return (
        WebsiteContent.objects.annotate(
            desc_len=Length(
                Cast(
                    NestableKeyTextTransform("metadata", *yt_description_fields),
                    CharField(),
                )
            )
        )
        .annotate(title_len=Length("title"))
        .filter(
            Q(website=website)
            & Q(**{query_resource_type_field: RESOURCE_TYPE_VIDEO})
            & (
                Q(desc_len__gt=YT_MAX_LENGTH_DESCRIPTION)
                | Q(title_len__gt=YT_MAX_LENGTH_TITLE)
            )
        )
    )


def videos_missing_captions(website: Website) -> List[WebsiteContent]:
    """Return a list of WebsiteContent objects for videos with unassigned captions"""
    if not is_ocw_site(website):
        return []
    query_resource_type_field = get_dict_query_field(
        "metadata", settings.FIELD_RESOURCETYPE
    )
    query_caption_field = get_dict_query_field("metadata", settings.YT_FIELD_CAPTIONS)
    return WebsiteContent.objects.filter(
        Q(website=website)
        & Q(**{query_resource_type_field: RESOURCE_TYPE_VIDEO})
        & (Q(**{query_caption_field: None}) | Q(**{query_caption_field: ""}))
    )


def mail_on_publish(website_name: str, version: str, success: bool, user_id: int):
    """Send a publishing success or failure message to the requesting user"""
    message = (
        PreviewOrPublishSuccessMessage if success else PreviewOrPublishFailureMessage
    )
    website = Website.objects.get(name=website_name)
    with get_message_sender(message) as sender:
        sender.build_and_send_message(
            User.objects.get(id=user_id),
            {
                "site": {
                    "title": website.title,
                    "url": website.get_full_url(version),
                },
                "version": version,
            },
        )


def detect_mime_type(uploaded_file: UploadedFile) -> str:
    """Detect mime type of an uploaded file"""
    magic = Magic(mime=True)
    chunk = next(uploaded_file.chunks(chunk_size=2048))
    return magic.from_buffer(chunk)


def reset_publishing_fields(website_name: str):
    """Reset all publishing fields to allow a fresh publish request"""
    now = now_in_utc()
    Website.objects.filter(name=website_name).update(
        has_unpublished_live=True,
        has_unpublished_draft=True,
        live_publish_status=None,
        draft_publish_status=None,
        live_publish_status_updated_on=now,
        draft_publish_status_updated_on=now,
        latest_build_id_live=None,
        latest_build_id_draft=None,
    )


def update_website_status(
    website: Website,
    version: str,
    status: str,
    update_time: datetime,
    unpublished=False,
):
    """Update some status fields in Website"""
    if version == VERSION_DRAFT:
        user = website.draft_last_published_by
        update_kwargs = {
            "draft_publish_status": status,
            "draft_publish_status_updated_on": update_time,
        }
        if status in PUBLISH_STATUSES_FINAL:
            if status == PUBLISH_STATUS_SUCCEEDED:
                update_kwargs["draft_publish_date"] = update_time
                update_kwargs["draft_last_published_by"] = None
            else:
                # Allow user to retry
                update_kwargs["has_unpublished_draft"] = True
    elif unpublished:
        user = website.last_unpublished_by
        update_kwargs = {
            "unpublish_status": status,
            "unpublish_status_updated_on": update_time,
            "live_publish_status": None,
            "live_publish_status_updated_on": None,
            "latest_build_id_live": None,
        }
    else:
        user = website.live_last_published_by
        update_kwargs = {
            "live_publish_status": status,
            "live_publish_status_updated_on": update_time,
        }
        if status in PUBLISH_STATUSES_FINAL:
            if status == PUBLISH_STATUS_SUCCEEDED:
                if website.first_published_to_production is None:
                    update_kwargs["first_published_to_production"] = update_time
                update_kwargs["publish_date"] = update_time
                update_kwargs["live_last_published_by"] = None
            else:
                # Allow user to retry
                update_kwargs["has_unpublished_live"] = True
    Website.objects.filter(name=website.name).update(**update_kwargs)
    if status in (PUBLISH_STATUS_ERRORED, PUBLISH_STATUS_ABORTED):
        log.error("A %s pipeline build failed for %s", version, website.name)
    if status in PUBLISH_STATUSES_FINAL and user and not unpublished:
        mail_on_publish(
            website.name, version, status == PUBLISH_STATUS_SUCCEEDED, user.id
        )


def incomplete_content_warnings(website):
    """
    Return array with error/warning messages for any website content missing expected data
    (currently: video youtube ids and captions).
    """
    missing_youtube_ids = videos_with_unassigned_youtube_ids(website)

    missing_youtube_ids_titles = [video.title for video in missing_youtube_ids]

    missing_captions_titles = [
        video.title for video in videos_missing_captions(website)
    ]

    truncatable_video_titles = [
        video.title for video in videos_with_truncatable_text(website)
    ]

    messages = []

    if len(missing_youtube_ids_titles) > 0:
        messages.append(
            f"The following video resources require YouTube IDs: {', '.join(missing_youtube_ids_titles)}"
        )
    if len(missing_captions_titles) > 0:
        messages.append(
            f"The following videos have missing captions: {', '.join(missing_captions_titles)}"
        )
    if len(truncatable_video_titles) > 0:
        messages.append(
            f"The following videos have titles or descriptions that will be truncated on YouTube: {', '.join(truncatable_video_titles)}"
        )

    return messages


def sync_website_title(content: WebsiteContent):
    """Sync sitemetadata title with Website.title"""
    title = get_dict_field(content.metadata, settings.FIELD_METADATA_TITLE)
    if title:
        content.website.title = title
        content.website.save()
