"""Tests for rewriting references to renamed legacy files."""

import pytest

from websites.filename_references import rewrite_file_references

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
