"""Tests for Concourse Steps"""

import json

import pytest
from django.test import override_settings
from ol_concourse.lib.models.pipeline import (
    GetStep,
    Identifier,
    PutStep,
    Step,
    TaskConfig,
    TaskStep,
)

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    SITE_CONTENT_GIT_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    LEARN_FASTLY_VAR,
    LIVE_FASTLY_VAR,
    ClearCdnCacheStep,
    ErrorHandlingStep,
    OcwStudioWebhookStep,
    OpenCatalogWebhookStep,
    SiteContentGitTaskStep,
    SlackAlertStep,
    add_error_handling,
)


def _build_mock_step(step_type):
    """Construct a minimal instance of step_type for error-handling tests"""
    if step_type is TaskStep:
        return step_type(config=TaskConfig(platform="linux"))
    return step_type()


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_add_error_handling(step_type):
    """Ensure that add_error_handling has all the correct steps"""
    mock_step = _build_mock_step(step_type)
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        short_id="test-site",
        instance_vars="?site:test-site",
    )
    for handler in [mock_step.on_failure, mock_step.on_error, mock_step.on_abort]:
        assert isinstance(handler, ErrorHandlingStep)
        steps = handler.try_.do
        types = [type(step) for step in steps]
        assert OcwStudioWebhookStep in types
        assert SlackAlertStep in types


def test_add_error_handling_incorrect_type():
    """Calling add_error_handling with the wrong type of step should throw a TypeError"""
    with pytest.raises(TypeError):  # noqa: PT012
        mock_step = Step()
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            short_id="test-site",
            instance_vars="?site:test-site",
        )


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_calling_add_error_handling_twice(step_type):
    """Calling add_error_handling twice on the same step should throw a ValueError"""
    mock_step = _build_mock_step(step_type)
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        short_id="test-site",
        instance_vars="?site:test-site",
    )
    with pytest.raises(ValueError):  # noqa: PT011
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            short_id="test-site",
            instance_vars="?site:test-site",
        )


def test_put_steps_empty_inputs():
    """Steps that extend PutStep and don't need inputs should explicitly set them to a blank list"""
    assert (
        json.loads(
            OcwStudioWebhookStep(
                pipeline_name="test_pipeline", status="test_status"
            ).model_dump_json(by_alias=True)
        )["try"]["inputs"]
        == []
    )
    assert (
        json.loads(
            OpenCatalogWebhookStep(
                pipeline_name="test_pipeline",
                site_url="http://ocw.mit.edu/courses/test_course",
                open_catalog_url="http://test_open_catalog/api/v0/ocw_next_webhook/",
            ).model_dump_json(by_alias=True)
        )["try"]["inputs"]
        == []
    )
    assert (
        json.loads(
            SlackAlertStep(alert_type="test_alert", text="test alert").model_dump_json(
                by_alias=True
            )
        )["try"]["do"][0]["inputs"]
        == []
    )


@pytest.mark.parametrize("concourse_is_private_repo", [True, False])
@pytest.mark.parametrize("branch", ["main", "test_branch"])
@pytest.mark.parametrize("short_id", ["course.1", "course.2"])
def test_site_content_git_task_step(
    settings, concourse_is_private_repo, branch, short_id
):
    """SiteContentGitTaskStep should have the proper attributes"""
    with override_settings(CONCOURSE_IS_PRIVATE_REPO=concourse_is_private_repo):
        step = SiteContentGitTaskStep(branch=branch, short_id=short_id)
        step_output = json.loads(step.model_dump_json())
        command = step_output["config"]["run"]["args"][1]
        if concourse_is_private_repo:
            assert "echo $GIT_PRIVATE_KEY > ./git.key" in command
            assert (
                'sed -i -E "s/(-----BEGIN[^-]+-----)(.+)(-----END[^-]+-----)/-----BEGINSSHKEY-----\\2\\-----ENDSSHKEY-----/" git.key'
                in command
            )
            assert 'sed -i -E "s/\\s/\\n/g" git.key' in command
            assert 'sed -i -E "s/SSHKEY/ OPENSSH PRIVATE KEY/g" git.key' in command
            assert "chmod 400 ./git.key" in command
            assert (
                f'git -c core.sshCommand="ssh $GIT_PRIVATE_KEY_FILE -o StrictHostKeyChecking=no" clone -b {branch} git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{short_id}.git ./{SITE_CONTENT_GIT_IDENTIFIER}'
                in command
            )
            assert step_output["params"]["GIT_PRIVATE_KEY"] == "((git-private-key))"
        else:
            assert f"git clone -b {branch} https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{short_id}.git ./{SITE_CONTENT_GIT_IDENTIFIER}"  # noqa: PLW0129
            assert step_output["params"] == {}


def _rendered_curl_args(fastly_var, site_name):
    """Render a ClearCdnCacheStep and return its curl arguments"""
    step = ClearCdnCacheStep(
        name=Identifier("clear-cdn-cache-test"),
        fastly_var=fastly_var,
        site_name=site_name,
    )
    rendered_step = json.loads(step.model_dump_json())
    return rendered_step["config"]["run"]["args"]


def _transfers(rendered_args):
    """
    Split rendered curl args into one list per transfer.

    curl resets most options at --next, so each transfer must carry its own -f and
    Fastly-Key. Global options are hoisted out before splitting.
    """
    global_flags = {"--fail-early"}
    transfers = [[]]
    for arg in rendered_args:
        if arg in global_flags:
            continue
        if arg == "--next":
            transfers.append([])
        else:
            transfers[-1].append(arg)
    return transfers


def _assert_transfer(transfer, fastly_var, site_name, *, soft_purge):
    """Assert that one curl transfer is a complete Fastly purge for fastly_var"""
    # -f is per-transfer: without it curl exits 0 on an HTTP error even under
    # --fail-early, so a failed purge would be reported as a successful publish
    assert "-f" in transfer
    assert transfer[transfer.index("-X") + 1] == "POST"
    assert transfer.count(f"Fastly-Key: (({fastly_var}.api_token))") == 1
    assert len([arg for arg in transfer if arg.startswith("Fastly-Key:")]) == 1
    purge_url = (
        f"https://api.fastly.com/service/(({fastly_var}.service_id))/purge/{site_name}"
    )
    assert transfer.count(purge_url) == 1
    assert len([arg for arg in transfer if arg.startswith("https://")]) == 1
    assert ("Fastly-Soft-Purge: 1" in transfer) == soft_purge


def test_clear_cdn_cache_step_live(settings, mock_concourse_hard_purge):
    """
    Assert that a live ClearCdnCacheStep purges both the live distribution and the
    MIT Learn distribution, each as a self-contained curl transfer.
    """
    site_name = "test_site"
    rendered_args = _rendered_curl_args(LIVE_FASTLY_VAR, site_name)
    # Concourse passes args straight to exec, so shell quoting must never appear
    for arg in rendered_args:
        assert "'" not in arg
    # --fail-early is global and must lead, otherwise curl exits 0 when the first
    # transfer fails and a later one succeeds
    assert rendered_args.count("--fail-early") == 1
    assert rendered_args.index("--fail-early") == 0
    transfers = _transfers(rendered_args)
    assert len(transfers) == 2
    soft_purge = not settings.CONCOURSE_HARD_PURGE
    _assert_transfer(transfers[0], LIVE_FASTLY_VAR, site_name, soft_purge=soft_purge)
    _assert_transfer(transfers[1], LEARN_FASTLY_VAR, site_name, soft_purge=soft_purge)


@pytest.mark.parametrize("fastly_var", ["fastly_draft", "fastly_test"])
def test_clear_cdn_cache_step_not_live(
    settings,
    mock_concourse_hard_purge,
    fastly_var,
):
    """
    Assert that a non-live ClearCdnCacheStep purges only its own distribution.
    Draft and test builds are not served through the MIT Learn distribution.
    """
    site_name = "test_site"
    rendered_args = _rendered_curl_args(fastly_var, site_name)
    for arg in rendered_args:
        assert "'" not in arg
    assert not any(LEARN_FASTLY_VAR in arg for arg in rendered_args)
    # A single transfer needs neither flag, keeping draft pipeline configs unchanged
    assert "--next" not in rendered_args
    assert "--fail-early" not in rendered_args
    transfers = _transfers(rendered_args)
    assert len(transfers) == 1
    _assert_transfer(
        transfers[0],
        fastly_var,
        site_name,
        soft_purge=not settings.CONCOURSE_HARD_PURGE,
    )


def test_no_get_property_on_put_steps():
    """Ensure that the no_get property is set on every class that extends PutStep"""
    slack_alert_step = SlackAlertStep(alert_type="test_alert", text="test alert")
    ocw_studio_webhook_step = OcwStudioWebhookStep(
        pipeline_name="test_pipeline", status="test_status"
    )
    open_catalog_webhook_step = OpenCatalogWebhookStep(
        site_url="http://ocw.mit.edu/courses/test_course",
        pipeline_name="test_pipeline",
        open_catalog_url="http://test_open_catalog/api/v0/ocw_next_webhook/",
    )
    slack_json = json.loads(slack_alert_step.model_dump_json())
    ocw_studio_json = json.loads(ocw_studio_webhook_step.model_dump_json())
    open_catalog_json = json.loads(open_catalog_webhook_step.model_dump_json())
    assert slack_json["try_"]["do"][0]["no_get"] is True
    assert ocw_studio_json["try_"]["no_get"] is True
    assert open_catalog_json["try_"]["no_get"] is True


@pytest.mark.parametrize("skip", [True, False])
def test_webhook_step_skip(skip):
    """Test that OcwStudioWebhookStep skips the webhook when skip=True."""
    step = OcwStudioWebhookStep(
        pipeline_name="test_pipeline",
        status="succeeded",
        theme_slug="some-theme",
        skip=skip,
    )
    step_json = json.loads(step.model_dump_json())

    if skip:
        assert step_json["try_"]["task"] == "ocw-studio-webhook-skipped"
        assert "put" not in step_json["try_"]
    else:
        assert step_json["try_"]["put"] is not None
        assert "task" not in step_json["try_"]
