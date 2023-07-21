"""Tests for Concourse Steps"""
import pytest
from ol_concourse.lib.models.pipeline import GetStep, PutStep, Step, TaskStep

from content_sync.pipelines.definitions.concourse.common.steps import (
    ErrorHandlingStep,
    OcwStudioWebhookStep,
    SlackAlertStep,
    add_error_handling,
)


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_add_error_handling(step_type):
    mock_step = step_type()
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        instance_vars_query_str="?site:test site",
    )
    for handler in [mock_step.on_failure, mock_step.on_error, mock_step.on_abort]:
        assert type(handler) == ErrorHandlingStep
        steps = handler.try_.do
        types = [type(step) for step in steps]
        assert OcwStudioWebhookStep in types
        assert SlackAlertStep in types


def test_add_error_handling_incorrect_type():
    with pytest.raises(TypeError):
        mock_step = Step()
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            instance_vars_query_str="?site:test site",
        )


@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_calling_add_error_handling_twice(step_type):
    mock_step = step_type()
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        instance_vars_query_str="?site:test site",
    )
    with pytest.raises(ValueError):
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            instance_vars_query_str="?site:test site",
        )
