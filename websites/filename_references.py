"""Rewrite stored references to files renamed by remove_uuid_from_filenames."""

import re
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

# A legacy file name: 32 hex characters, an underscore, then the rest of the
# name. "?" and "#" end it, so a query string or fragment is not read as part
# of the name. The lookbehind stops a match starting inside a longer hex run.
FILENAME_TOKEN_RE = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}_[^\s\"'<>()\[\]|\\/?#=]+"
)

# A path prefix with no delimiters in it, ending in the directory that holds
# the token, e.g. "https://ocw.mit.edu/courses/site/" or "/courses/site/".
_PATH_PREFIX_RE = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*://[^/]+)?/?((?:[^/?#]+/)+)")

# Characters that cannot be part of a path, so the prefix scan stops there.
_DELIMITERS = frozenset(" \t\r\n\"'<>()[]|\\=")

# How far back to look for a token's directory. Real paths are far shorter.
_DIRECTORY_LOOKBACK = 2048

_TRAILING_PUNCTUATION = ".,;:!?"

PathLookup = Mapping[tuple[str, str], str]


def rewrite_file_references(text: str, lookup: PathLookup) -> str:
    """
    Replace the file name in every path reference to a renamed file.

    Only a reference with a directory in front of it is rewritten, since the
    directory is what ties a name to one site. Bare names are the gallery
    patcher's job. Everything except the file name, including a host and a
    leading slash, stays exactly as written.
    """
    if not text or not lookup:
        return text
    pieces = []
    last = 0
    for match in FILENAME_TOKEN_RE.finditer(text):
        directory = _directory_before(text, match.start())
        if directory is None:
            continue
        found = _resolve(lookup, directory, match.group(0))
        if found is None:
            continue
        new_name, old_length = found
        pieces.append(text[last : match.start()])
        pieces.append(new_name)
        last = match.start() + old_length
    if not pieces:
        return text
    pieces.append(text[last:])
    return "".join(pieces)


def _directory_before(text: str, end: int) -> str | None:
    """Return the directory that ends right at *end*, without slashes, or None."""
    start = end
    floor = max(0, end - _DIRECTORY_LOOKBACK)
    while start > floor and text[start - 1] not in _DELIMITERS:
        start -= 1
    match = _PATH_PREFIX_RE.fullmatch(text, start, end)
    if match is None:
        return None
    return match.group(1).strip("/")


def _resolve(lookup: PathLookup, directory: str, name: str) -> tuple[str, int] | None:
    """
    Look *name* up under *directory*, retrying without trailing punctuation.

    Returns the new name and how many characters of *name* it replaces, so a
    full stop right after a link survives the rewrite.
    """
    new_name = lookup.get((directory, name))
    if new_name is not None:
        return new_name, len(name)
    trimmed = name.rstrip(_TRAILING_PUNCTUATION)
    if trimmed != name:
        new_name = lookup.get((directory, trimmed))
        if new_name is not None:
            return new_name, len(trimmed)
    return None


class _RenameLike(Protocol):
    old_key: str
    new_key: str
    website_id: str


def build_path_index(
    renames: Iterable[_RenameLike],
    site_paths: Mapping[str, tuple[str | None, str | None]],
) -> dict[tuple[str, str], _RenameLike]:
    """
    Map (directory, old file name) to the rename it belongs to.

    The directory is the old key's own, not the website's, because a few
    duplicate site records store their files under another site's directory.
    A reference can also use the published path, so when the directory is
    the website's s3_path and its url_path differs, the url_path gets an
    entry too. *site_paths* maps website id to (s3_path, url_path).
    """
    index = {}
    for rename in renames:
        old_directory, _, old_name = rename.old_key.strip("/").rpartition("/")
        index[(old_directory, old_name)] = rename
        s3_path, url_path = site_paths.get(rename.website_id, (None, None))
        s3_directory = (s3_path or "").strip("/")
        url_directory = (url_path or "").strip("/")
        if (
            url_directory
            and old_directory == s3_directory
            and url_directory != s3_directory
        ):
            index[(url_directory, old_name)] = rename
    return index


def build_path_lookup(
    renames: Iterable[_RenameLike],
    site_paths: Mapping[str, tuple[str | None, str | None]],
) -> dict[tuple[str, str], str]:
    """Map (directory, old file name) to the new file name for every rename."""
    return {
        entry: rename.new_key.rpartition("/")[2]
        for entry, rename in build_path_index(renames, site_paths).items()
    }


def referenced_entries(text: str | None, entries: Mapping) -> set[tuple[str, str]]:
    """
    Return the (directory, old file name) keys of *entries* that *text* names.

    Uses the same matching as rewrite_file_references, so a row is only
    handed to a chunk when that chunk's rewrite would change it.
    """
    found = set()
    if not text or not entries:
        return found
    for match in FILENAME_TOKEN_RE.finditer(text):
        directory = _directory_before(text, match.start())
        if directory is None:
            continue
        resolved = _resolve(entries, directory, match.group(0))
        if resolved is not None:
            found.add((directory, match.group(0)[: resolved[1]]))
    return found


def referenced_entries_in_json(value: Any, entries: Mapping) -> set[tuple[str, str]]:
    """Return referenced_entries for every string inside a JSON-shaped value."""
    if isinstance(value, str):
        return referenced_entries(value, entries)
    if isinstance(value, dict):
        return set().union(
            *(referenced_entries_in_json(item, entries) for item in value.values())
        )
    if isinstance(value, list):
        return set().union(
            *(referenced_entries_in_json(item, entries) for item in value)
        )
    return set()


def rewrite_json_strings(value: Any, lookup: PathLookup) -> tuple[Any, bool]:
    """
    Rewrite file references in every string inside a JSON-shaped value.

    Returns (value, changed). Keys are left alone. An unchanged value comes
    back as the same object, so callers can skip it cheaply.
    """
    if isinstance(value, str):
        rewritten = rewrite_file_references(value, lookup)
        return rewritten, rewritten != value
    if isinstance(value, dict):
        items = {key: rewrite_json_strings(item, lookup) for key, item in value.items()}
        if not any(changed for _, changed in items.values()):
            return value, False
        return {key: item for key, (item, _) in items.items()}, True
    if isinstance(value, list):
        items = [rewrite_json_strings(item, lookup) for item in value]
        if not any(changed for _, changed in items):
            return value, False
        return [item for item, _ in items], True
    return value, False
