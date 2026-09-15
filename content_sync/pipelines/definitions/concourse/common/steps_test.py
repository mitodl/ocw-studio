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

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    SITE_CONTENT_GIT_IDENTIFIER,
    get_fastly_identifier,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    FASTLY_PURPOSE_LEARN,
    FASTLY_PURPOSE_TEST,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    ErrorHandlingStep,
    OcwStudioWebhookStep,
    OpenCatalogWebhookStep,
    SiteContentGitTaskStep,
    SlackAlertStep,
    add_error_handling,
    clear_cdn_cache_steps,
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
    assert (
        json.loads(
            ClearCdnCacheStep(
                name=Identifier("clear-cdn-cache-test"),
                purpose=VERSION_LIVE,
                site_name="test_site",
            ).model_dump_json(by_alias=True)
        )["inputs"]
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


def _rendered_steps(purpose, site_name):
    """Render the purge steps for a purpose and return them as dicts"""
    return [
        json.loads(step.model_dump_json(exclude_none=True))
        for step in clear_cdn_cache_steps(
            name=Identifier("clear-cdn-cache-test"),
            purpose=purpose,
            site_name=site_name,
        )
    ]


def _assert_purge_step(step, purpose, site_name, *, soft_purge):
    """Assert that a rendered step is a complete Fastly purge for one distribution"""
    assert step["resource"] == get_fastly_identifier(purpose)
    assert step["params"]["mode"] == "surrogate_key"
    assert step["params"]["surrogate_key"] == site_name
    # soft is only sent when soft-purging; the resource defaults it to false
    assert step["params"].get("soft", False) == soft_purge
    # A put with neither would make Concourse run an implicit get of a version the
    # resource never publishes, and would consume the job's inputs
    assert step["no_get"] is True
    assert step["inputs"] == []
    # The resource has no internal retry of its own
    assert step["attempts"] == 3
    assert step["timeout"] == "5m"


def test_clear_cdn_cache_step_live(settings, mock_concourse_hard_purge):
    """
    Assert that a live build purges both the live distribution and the MIT Learn
    distribution, as two puts against two separate Fastly resources.
    """
    site_name = "test_site"
    steps = _rendered_steps(VERSION_LIVE, site_name)
    assert len(steps) == 2
    soft_purge = not settings.CONCOURSE_HARD_PURGE
    _assert_purge_step(steps[0], VERSION_LIVE, site_name, soft_purge=soft_purge)
    _assert_purge_step(steps[1], FASTLY_PURPOSE_LEARN, site_name, soft_purge=soft_purge)
    # The primary purge keeps the step name it is given; only the extra one is
    # suffixed, so build history and Slack alerts stay readable
    assert steps[0]["put"] == "clear-cdn-cache-test"
    assert steps[1]["put"] == f"clear-cdn-cache-test-{FASTLY_PURPOSE_LEARN}"


@pytest.mark.parametrize("purpose", [VERSION_DRAFT, FASTLY_PURPOSE_TEST])
def test_clear_cdn_cache_step_not_live(
    settings,
    mock_concourse_hard_purge,
    purpose,
):
    """
    Assert that a non-live build purges only its own distribution. Draft and test
    builds are not served through the MIT Learn distribution.
    """
    site_name = "test_site"
    steps = _rendered_steps(purpose, site_name)
    assert len(steps) == 1
    _assert_purge_step(
        steps[0],
        purpose,
        site_name,
        soft_purge=not settings.CONCOURSE_HARD_PURGE,
    )
    assert steps[0]["put"] == "clear-cdn-cache-test"
    assert get_fastly_identifier(FASTLY_PURPOSE_LEARN) not in json.dumps(steps)


def test_clear_cdn_cache_step_omitted_without_domain(settings):
    """
    Assert that a distribution with no configured domain is omitted rather than
    rendering a purge that cannot resolve a Fastly service. CI has no OCW Fastly
    service at all.
    """
    settings.OCW_STUDIO_LIVE_URL = None
    settings.COURSE_V3_CANONICAL_DOMAIN = None
    assert _rendered_steps(VERSION_LIVE, "test_site") == []


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
    clear_cdn_cache_step = ClearCdnCacheStep(
        name=Identifier("clear-cdn-cache-test"),
        purpose=VERSION_LIVE,
        site_name="test_site",
    )
    slack_json = json.loads(slack_alert_step.model_dump_json())
    ocw_studio_json = json.loads(ocw_studio_webhook_step.model_dump_json())
    open_catalog_json = json.loads(open_catalog_webhook_step.model_dump_json())
    clear_cdn_cache_json = json.loads(clear_cdn_cache_step.model_dump_json())
    assert slack_json["try_"]["do"][0]["no_get"] is True
    assert ocw_studio_json["try_"]["no_get"] is True
    assert open_catalog_json["try_"]["no_get"] is True
    assert clear_cdn_cache_json["no_get"] is True


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
