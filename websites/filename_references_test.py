"""Tests for rewriting references to renamed legacy files."""

from types import SimpleNamespace

import pytest

from websites.filename_references import (
    build_path_lookup,
    rewrite_file_references,
    rewrite_json_strings,
)

UUID = "cc3d029952cda060f4afcd811189a591"  # pragma: allowlist secret
LOOKUP = {("courses/site", f"{UUID}_1.jpg"): "1-3.jpg"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            f"https://ocw.mit.edu/courses/site/{UUID}_1.jpg",
            "https://ocw.mit.edu/courses/site/1-3.jpg",
        ),
        (f"/courses/site/{UUID}_1.jpg", "/courses/site/1-3.jpg"),
        (f"courses/site/{UUID}_1.jpg", "courses/site/1-3.jpg"),
        (f"![a](/courses/site/{UUID}_1.jpg)", "![a](/courses/site/1-3.jpg)"),
        (f"see /courses/site/{UUID}_1.jpg.", "see /courses/site/1-3.jpg."),
        (f"/courses/site/{UUID}_1.jpg?raw=1", "/courses/site/1-3.jpg?raw=1"),
        (f'href=/courses/site/{UUID}_1.jpg"', 'href=/courses/site/1-3.jpg"'),
        (
            f"/courses/site/{UUID}_1.jpg and /courses/site/{UUID}_1.jpg",
            "/courses/site/1-3.jpg and /courses/site/1-3.jpg",
        ),
    ],
)
def test_rewrites_path_references(text, expected):
    """Only the file name changes. Host, directory and slash stay as written."""
    assert rewrite_file_references(text, LOOKUP) == expected


@pytest.mark.parametrize(
    "text",
    [
        f"{UUID}_1.jpg",  # bare name, left to the gallery patcher
        f'href="{UUID}_1.jpg"',  # bare name inside an attribute
        f"/courses/site/{UUID}_1.jpg.bak",  # a different, longer name
        f"/courses/site/f{UUID}_1.jpg",  # starts inside a longer hex run
        f"/courses/other/{UUID}_1.jpg",  # same name in a directory not renamed
        "no references here",
        "",
    ],
)
def test_leaves_other_text_alone(text):
    """Anything that is not a directory-qualified renamed name is unchanged."""
    assert rewrite_file_references(text, LOOKUP) == text


def test_empty_lookup_changes_nothing():
    """With no renames there is nothing to rewrite."""
    text = f"/courses/site/{UUID}_1.jpg"
    assert rewrite_file_references(text, {}) == text


def _rename(old_key, new_key, website_id="site-1"):
    return SimpleNamespace(old_key=old_key, new_key=new_key, website_id=website_id)


def test_lookup_is_keyed_by_the_old_keys_own_directory():
    """A leading slash on the stored key does not change the entry."""
    lookup = build_path_lookup(
        [_rename(f"/courses/site/{UUID}_1.jpg", "/courses/site/1-3.jpg")], {}
    )

    assert lookup == {("courses/site", f"{UUID}_1.jpg"): "1-3.jpg"}


def test_lookup_adds_the_published_path_when_it_differs():
    """A reference through url_path resolves when the file sits under s3_path."""
    lookup = build_path_lookup(
        [_rename(f"sites/store/{UUID}_1.jpg", "sites/store/1-3.jpg")],
        {"site-1": ("sites/store", "courses/published")},
    )

    assert lookup == {
        ("sites/store", f"{UUID}_1.jpg"): "1-3.jpg",
        ("courses/published", f"{UUID}_1.jpg"): "1-3.jpg",
    }


def test_lookup_skips_the_published_path_for_files_elsewhere():
    """A file stored under another site's directory gets no url_path alias."""
    lookup = build_path_lookup(
        [_rename(f"courses/home/{UUID}_1.jpg", "courses/home/1.jpg")],
        {"site-1": ("courses/duplicate", "courses/duplicate-published")},
    )

    assert lookup == {("courses/home", f"{UUID}_1.jpg"): "1.jpg"}


def test_rewrites_every_string_in_nested_json():
    """Values anywhere in the structure are rewritten, keys are not."""
    value = {
        "file": f"/courses/site/{UUID}_1.jpg",
        f"{UUID}_1.jpg": "the key stays",
        "video_files": {"captions": [f"courses/site/{UUID}_1.jpg", None, 3]},
    }

    rewritten, changed = rewrite_json_strings(value, LOOKUP)

    assert changed is True
    assert rewritten == {
        "file": "/courses/site/1-3.jpg",
        f"{UUID}_1.jpg": "the key stays",
        "video_files": {"captions": ["courses/site/1-3.jpg", None, 3]},
    }


def test_unchanged_json_is_returned_as_the_same_object():
    """Nothing to rewrite means no copy and changed is False."""
    value = {"resourcetype": "Document", "video_files": None}

    rewritten, changed = rewrite_json_strings(value, LOOKUP)

    assert changed is False
    assert rewritten is value


def test_none_json_is_left_alone():
    """Content can have null metadata."""
    assert rewrite_json_strings(None, LOOKUP) == (None, False)
