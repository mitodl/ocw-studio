import json

import pytest

from content_sync.constants import (
    OCW_HUGO_PRODUCTION_TAG_REGEX,
    OCW_HUGO_RC_TAG_REGEX,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    FASTLY_PURPOSE_LEARN,
    FASTLY_PURPOSE_TEST,
    GitResource,
    OcwHugoProjectsGitResource,
    OcwHugoThemesGitResource,
    fastly_resources,
    get_fastly_service_id,
)


@pytest.mark.parametrize(
    ("purpose", "service_id"),
    [
        (VERSION_DRAFT, "((fastly_draft.service_id))"),
        (VERSION_LIVE, "((fastly_live.service_id))"),
        (FASTLY_PURPOSE_LEARN, "((fastly_learn.service_id))"),
        (FASTLY_PURPOSE_TEST, "((fastly_test.service_id))"),
        ("unknown", ""),
    ],
)
def test_get_fastly_service_id(purpose, service_id):
    """The Fastly service ID should match the Concourse variable for the purpose."""
    assert get_fastly_service_id(purpose) == service_id


@pytest.mark.parametrize(
    ("purpose", "service_ids", "domains"),
    [
        (
            VERSION_DRAFT,
            ["((fastly_draft.service_id))"],
            ["draft.ocw.mit.edu"],
        ),
        (
            VERSION_LIVE,
            ["((fastly_live.service_id))", "((fastly_learn.service_id))"],
            ["live.ocw.mit.edu", "learn-test.mit.edu"],
        ),
        (
            FASTLY_PURPOSE_TEST,
            ["((fastly_test.service_id))"],
            ["test.ocw.mit.edu"],
        ),
    ],
)
def test_fastly_resources_use_service_ids_and_domains(
    settings, purpose, service_ids, domains
):
    """Fastly purge resources should include service IDs and domains."""
    resources = [
        json.loads(resource.model_dump_json(exclude_none=True))
        for resource in fastly_resources(purpose)
    ]

    assert [resource["source"]["service_id"] for resource in resources] == service_ids
    assert [resource["source"]["domain"] for resource in resources] == domains
    assert all(resource["check_every"] == "never" for resource in resources)
    assert all(
        resource["source"]["api_token"] == settings.CONCOURSE_FASTLY_API_TOKEN_VAR
        for resource in resources
    )


def test_git_resource_follows_a_branch_by_default():
    """A git resource without a tag pattern follows its branch"""
    resource = GitResource(name="repo", uri="https://example.com/repo.git", branch="x")
    assert resource.source == {"uri": "https://example.com/repo.git", "branch": "x"}


def test_git_resource_with_a_tag_regex_follows_tags():
    """A tag pattern replaces the branch, and the newest version sorts last"""
    resource = GitResource(
        name="repo",
        uri="https://example.com/repo.git",
        branch="x",
        tag_regex=OCW_HUGO_RC_TAG_REGEX,
    )
    assert resource.source == {
        "uri": "https://example.com/repo.git",
        "version_type": "tags",
        "tag_regex": OCW_HUGO_RC_TAG_REGEX,
        "tag_sort": "version",
    }


@pytest.mark.parametrize(
    ("tag_releases", "pointer", "expected_regex"),
    [
        (True, "release-candidate", OCW_HUGO_RC_TAG_REGEX),
        (True, "release", OCW_HUGO_PRODUCTION_TAG_REGEX),
        (True, "main", None),
        (False, "release-candidate", None),
        (False, "release", None),
    ],
)
def test_ocw_hugo_git_resources_follow_tags_only_for_release_pointers(
    mocker, settings, tag_releases, pointer, expected_regex
):
    """ocw-hugo-themes and ocw-hugo-projects follow tags only when tag releases are on"""
    settings.OCW_HUGO_TAG_RELEASES = tag_releases
    mocker.patch("content_sync.utils.is_dev", return_value=False)
    for resource in (
        OcwHugoThemesGitResource(branch=pointer),
        OcwHugoProjectsGitResource(
            uri="https://github.com/mitodl/ocw-hugo-projects.git", branch=pointer
        ),
    ):
        if expected_regex:
            assert resource.source["version_type"] == "tags"
            assert resource.source["tag_regex"] == expected_regex
            assert "branch" not in resource.source
        else:
            assert resource.source["branch"] == pointer
            assert "version_type" not in resource.source
