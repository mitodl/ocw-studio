"""Tests for Concourse Steps"""
import pytest
from ol_concourse.lib.models.pipeline import GetStep, PutStep, Step, TaskStep

from content_sync.pipelines.definitions.concourse.common.steps import (
    OcwStudioWebhookStep,
    SlackAlertStep,
    add_error_handling,
)


@pytest.mark.parametrize("is_dev", [True, False])
@pytest.mark.parametrize("step_type", [GetStep, PutStep, TaskStep])
def test_add_error_handling(mocker, is_dev, step_type):
    is_dev_mock = mocker.patch(
        "content_sync.pipelines.definitions.concourse.common.steps.is_dev"
    )
    is_dev_mock.return_value = is_dev
    mock_step = step_type()
    add_error_handling(
        step=mock_step,
        step_description="test step",
        pipeline_name="test_pipeline",
        instance_vars_query_str="?site:test site",
    )
    handlers = [mock_step.on_failure, mock_step.on_error, mock_step.on_abort]
    for handler in handlers:
        assert handler is not None
        steps = handler.try_.do
        types = []
        for step in steps:
            types.append(type(step))
        if is_dev:
            assert OcwStudioWebhookStep in types
            assert SlackAlertStep not in types
        else:
            assert OcwStudioWebhookStep in types
            assert SlackAlertStep in types
    print(mock_step.json(indent=2))


def test_add_error_handling_incorrect_type():
    with pytest.raises(TypeError):
        mock_step = Step()
        add_error_handling(
            step=mock_step,
            step_description="test step",
            pipeline_name="test_pipeline",
            instance_vars_query_str="?site:test site",
        )
