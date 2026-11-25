"""
One parser for caption and transcript file names.

Drive sync, publish-time linking and language resolution all read names
through it, so they agree on which video a file belongs to and which language
it is in.

A name is the video's name, a keyword and the real extension, with an optional
language code right after the keyword (optionally followed by a two-letter
locale) or right before it:

    lecture-1_captions.vtt, lecture-1_captions-es.vtt, lecture-1_captions.es.vtt,
    Lecture_1-Captions-pt-BR.vtt, lecture-1_es_captions.vtt,
    lecture-1_transcript_fr.pdf

Case is ignored, and runs of "-", "_", "." and spaces count as one separator.
Only codes in the site's language list count as a language. Other tokens after
the keyword ("300k", "2", "old") are ignored.
"""

import re
from dataclasses import dataclass
from functools import reduce
from operator import or_
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q

from videos.constants import CAPTION_FILE_EXTENSIONS, TRANSCRIPT_FILE_EXTENSIONS
from videos.utils import clean_uuid_filename, get_video_base_filename
from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_VIDEO
from websites.models import WebsiteContent
from websites.site_config_api import SiteConfig
from websites.utils import get_dict_query_field

if TYPE_CHECKING:
    from collections.abc import Collection

    from websites.models import Website

CAPTIONS = "captions"
TRANSCRIPT = "transcript"

_KEYWORD_KINDS = {
    "caption": CAPTIONS,
    "captions": CAPTIONS,
    "transcript": TRANSCRIPT,
    "transcripts": TRANSCRIPT,
}
_SEPARATOR_RE = re.compile(r"[-_.\s]+")
_LOCALE_RE = re.compile(r"^[a-z]{2}$")
LANGUAGE_FIELD = "language"


@dataclass(frozen=True)
class ParsedCaptionName:
    """What a caption or transcript file name says about its video and language"""

    kind: str
    # Normalized video names the file can belong to, most specific first
    video_keys: tuple[str, ...]
    language: str | None
    locale: str | None


def _tokens(name: str) -> list[str]:
    """Split a name into lowercase tokens on runs of separators"""
    return [token for token in _SEPARATOR_RE.split(name.lower()) if token]


def video_name_key(name: str) -> str:
    """Return a name with case and separators normalized, for comparing names"""
    return "-".join(_tokens(name or ""))


def _kind_for_extension(extension: str) -> str | None:
    """Return the file kind that a real file extension stands for"""
    if extension in CAPTION_FILE_EXTENSIONS:
        return CAPTIONS
    if extension in TRANSCRIPT_FILE_EXTENSIONS:
        return TRANSCRIPT
    return None


def parse_caption_filename(
    name: str, languages: Collection[str]
) -> ParsedCaptionName | None:
    """
    Parse a caption or transcript file name, such as "lecture-1_captions-es.vtt".

    Pass the real file name with its extension (the original Drive name when
    there is one, see caption_source_name). Returns None when the extension is
    not a caption or transcript extension, when the name has no keyword or the
    last keyword disagrees with the extension, or when no video name comes
    before the keyword.
    """
    stem, dot, extension = PurePosixPath(name or "").name.rpartition(".")
    if not dot:
        return None
    kind = _kind_for_extension(extension.lower())
    if kind is None:
        return None

    tokens = _tokens(stem)
    keyword_index = next(
        (
            index
            for index in range(len(tokens) - 1, -1, -1)
            if tokens[index] in _KEYWORD_KINDS
        ),
        None,
    )
    if keyword_index is None or _KEYWORD_KINDS[tokens[keyword_index]] != kind:
        return None
    before, after = tokens[:keyword_index], tokens[keyword_index + 1 :]
    if not before:
        return None

    codes = {code.lower() for code in languages}
    video_keys = ("-".join(before),)
    language = locale = None
    if after and after[0] in codes:
        language = after[0]
        if len(after) > 1 and _LOCALE_RE.match(after[1]):
            locale = after[1].upper()
    elif len(before) > 1 and before[-1] in codes:
        # "lecture_es_captions.vtt" belongs to a video named "lecture-es" if
        # there is one, else it is the Spanish file of "lecture".
        language = before[-1]
        video_keys = ("-".join(before), "-".join(before[:-1]))
    return ParsedCaptionName(kind, video_keys, language, locale)


def site_languages(website: Website) -> frozenset[str]:
    """
    Return the language codes a site's resources can be tagged with.

    These are the option values of the "language" field on the starter's
    resource item. A starter without that field gives an empty set.
    """
    starter = website.starter
    if starter is None or not starter.config:
        return frozenset()
    item = SiteConfig(starter.config).find_item_by_name(CONTENT_TYPE_RESOURCE)
    if item is None:
        return frozenset()
    field = next(
        (field for field in item.fields if field.get("name") == LANGUAGE_FIELD),
        None,
    )
    if field is None:
        return frozenset()
    codes = set()
    for option in field.get("options") or []:
        value = option.get("value") if isinstance(option, dict) else option
        if isinstance(value, str) and value.strip():
            codes.add(value.strip().lower())
    return frozenset(codes)


def caption_source_name(resource: WebsiteContent) -> str | None:
    """
    Return the file name to parse for a caption or transcript resource.

    The original Drive name wins, because the S3 key Drive sync writes drops
    dots ("captions.es" becomes "captionses"). Otherwise the uploaded file's
    name is used, without the text_id prefix Studio adds to uploads.
    """
    # .all() rather than .first() so a prefetch_related("drivefile_set") is used
    drive_file = min(resource.drivefile_set.all(), key=lambda df: df.pk, default=None)
    if drive_file is not None and drive_file.name:
        return drive_file.name
    file_name = getattr(getattr(resource, "file", None), "name", None)
    if not file_name:
        return None
    return clean_uuid_filename(PurePosixPath(file_name).name)


RELATION_FIELDS = {
    CAPTIONS: "video_captions_resources",
    TRANSCRIPT: "video_transcript_resources",
}


def _video_key(video_resource: WebsiteContent) -> str:
    """Return the normalized name of a video resource, without its extension"""
    return video_name_key(get_video_base_filename(video_resource.filename))


def _site_video_resources(website: Website):
    """Return the site's Video resources in a stable order"""
    return WebsiteContent.objects.filter(
        website=website,
        **{
            get_dict_query_field(
                "metadata", settings.FIELD_RESOURCETYPE
            ): RESOURCE_TYPE_VIDEO
        },
    ).order_by("filename", "pk")


def _owning_key(parsed: ParsedCaptionName, video_keys: Collection[str]) -> str | None:
    """Return the most specific of a file's video names that a video has"""
    return next((key for key in parsed.video_keys if key in video_keys), None)


def find_caption_files(
    video_resource: WebsiteContent,
) -> tuple[list[WebsiteContent], list[WebsiteContent]]:
    """
    Return a video resource's caption and transcript files, ordered by filename.

    A file belongs to the video when its parsed video name equals the video's
    name without its extension. When a file could belong to two videos
    ("lecture_es_captions.vtt" next to "lecture_mp4" and "lecture-es_mp4"), the
    longer video name wins.
    """
    key = _video_key(video_resource)
    if not key:
        return [], []
    website = video_resource.website
    video_keys = {_video_key(video) for video in _site_video_resources(website)}
    video_keys.add(key)
    languages = site_languages(website)
    extension_filter = reduce(
        or_,
        (
            Q(file__iendswith=f".{extension}")
            for extension in (*CAPTION_FILE_EXTENSIONS, *TRANSCRIPT_FILE_EXTENSIONS)
        ),
    )
    candidates = (
        WebsiteContent.objects.filter(extension_filter, website=website)
        .prefetch_related("drivefile_set")
        .order_by("filename")
    )
    found = {CAPTIONS: [], TRANSCRIPT: []}
    for resource in candidates:
        parsed = parse_caption_filename(caption_source_name(resource), languages)
        if parsed and _owning_key(parsed, video_keys) == key:
            found[parsed.kind].append(resource)
    return found[CAPTIONS], found[TRANSCRIPT]


def find_video_for_caption(
    resource: WebsiteContent,
) -> tuple[WebsiteContent, str] | None:
    """
    Return the Video resource a caption or transcript file belongs to, and the
    relation field ("video_captions_resources" or "video_transcript_resources")
    to add it to. Returns None when the name matches no Video resource.
    """
    website = resource.website
    parsed = parse_caption_filename(
        caption_source_name(resource), site_languages(website)
    )
    if parsed is None:
        return None
    videos_by_key = {}
    for video in _site_video_resources(website):
        videos_by_key.setdefault(_video_key(video), video)
    key = _owning_key(parsed, videos_by_key)
    if key is None:
        return None
    return videos_by_key[key], RELATION_FIELDS[parsed.kind]
