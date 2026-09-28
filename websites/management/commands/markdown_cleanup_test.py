"""Tests for the markdown_cleanup management command."""  # noqa: INP001

from websites.management.commands.markdown_cleanup import Command


def test_rule_aliases_are_unique_and_non_empty():
    """Every registered rule must have a distinct, non-empty --alias value."""
    aliases = [rule.alias for rule in Command.Rules]
    assert all(aliases), "a rule is missing its alias"
    assert len(aliases) == len(set(aliases)), "duplicate rule alias found"


def test_gallery_image_rename_is_a_registered_alias():
    """gallery_image_rename must be selectable via --alias for RC/backfill repair runs."""
    aliases = [rule.alias for rule in Command.Rules]
    assert "gallery_image_rename" in aliases
