"""Tests for Concourse Steps"""
import json

import pytest
from django.test import override_settings
from ol_concourse.lib.models.pipeline import GetStep, PutStep, Step, TaskStep

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    SITE_CONTENT_GIT_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ErrorHandlingStep,
    OcwStudioWebhookStep,
    SiteContentGitTaskStep,
    SlackAlertStep,
    add_error_handling,
)


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_add_error_handling(step_type):
    """ensure that add_error_handling has all the correct steps"""
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
    """calling add_error_handling with the wrong type of step should throw a TypeError"""
    with pytest.raises(TypeError):
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
    """calling add_error_handling twice on the same step should throw a ValueError"""
    mock_step = step_type()
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        short_id="test-site",
        instance_vars="?site:test-site",
    )
    with pytest.raises(ValueError):
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            short_id="test-site",
            instance_vars="?site:test-site",
        )


def test_put_steps_empty_inputs():
    """steps that extend PutStep and don't need inputs should explicitly set them to a blank list"""
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
            OpenDiscussionsWebhookStep(
                pipeline_name="test_pipeline",
                site_url="http://ocw.mit.edu/courses/test_course",
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
