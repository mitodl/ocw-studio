"""Rewrite stored references to files renamed by remove_uuid_from_filenames."""

import re
from collections.abc import Mapping

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
