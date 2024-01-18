"""Tests for Concourse Steps"""
import json

import pytest
from django.test import override_settings
from ol_concourse.lib.models.pipeline import (
    GetStep,
    Identifier,
    PutStep,
    Step,
    TaskStep,
)

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    SITE_CONTENT_GIT_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    ErrorHandlingStep,
    OcwStudioWebhookStep,
    OpenCatalogWebhookStep,
    SiteContentGitTaskStep,
    SlackAlertStep,
    add_error_handling,
)


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_add_error_handling(step_type):
    """Ensure that add_error_handling has all the correct steps"""
    mock_step = step_type()
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        short_id="test-site",
        instance_vars="?site:test-site",
    )
    for handler in [mock_step.on_failure, mock_step.on_error, mock_step.on_abort]:
        assert type(handler) == ErrorHandlingStep
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
    mock_step = step_type()
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


def test_clear_cdn_cache_step(settings, mock_concourse_hard_purge):
    """Assert that the ClearCdnCacheStep renders with the correct attributes"""
    name = Identifier("clear-cdn-cache-test")
    fastly_var = "fastly_test"
    site_name = "test_site"
    clear_cdn_cache_step = ClearCdnCacheStep(
        name=name,
        fastly_var=fastly_var,
        site_name=site_name,
    )
    rendered_step = json.loads(clear_cdn_cache_step.model_dump_json())
    rendered_args = rendered_step["config"]["run"]["args"]
    for arg in rendered_args:
        assert "'" not in arg
    assert f"Fastly-Key: (({fastly_var}.api_token))" in rendered_args
    if settings.CONCOURSE_HARD_PURGE:
        assert "Fastly-Soft-Purge: 1" not in rendered_args
    else:
        assert "Fastly-Soft-Purge: 1" in rendered_args
    assert (
        f"https://api.fastly.com/service/(({fastly_var}.service_id))/purge/{site_name}"
        in rendered_args
    )
