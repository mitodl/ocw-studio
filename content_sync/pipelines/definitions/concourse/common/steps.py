import json
from urllib.parse import urljoin

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    DoStep,
    GetStep,
    Identifier,
    PutStep,
    StepModifierMixin,
    TaskConfig,
    TaskStep,
    TryStep,
)

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    CURL_REGISTRY_IMAGE,
)


def add_error_handling(
    step: StepModifierMixin,
    step_description: str,
    pipeline_name: str,
    instance_vars_query_str: str,
):
    """
    Add error handling steps to any Step-like object

    Args:
        step(StepModifierMixin): The Step-like object that uses StepModifierMixin to add the error handling steps to
        step_description(str): A description of the step at which the failure occurred
        instance_vars_query_str(str): A query string of the instance vars from the pipeline to build a URL with

    Returns:
        None
    """
    step_type = type(step)
    if not issubclass(step_type, StepModifierMixin):
        raise TypeError(
            f"The step object of type {step_type} does not extend StepModifierMixin and therefore cannot have error handling"
        )
    for failure_step in [step.on_failure, step.on_error, step.on_abort]:
        if failure_step is not None:
            raise ValueError(f"The step {step} already has {failure_step} set")
    concourse_base_url = settings.CONCOURSE_URL
    concourse_team = settings.CONCOURSE_TEAM
    concourse_path = (
        f"/teams/{concourse_team}/pipelines/{pipeline_name}{instance_vars_query_str}"
    )
    concourse_url = urljoin(concourse_base_url, concourse_path)
    step.on_failure = ErrorHandlingStep(
        pipeline_name=pipeline_name,
        status="failed",
        failure_description="Failed",
        step_description=step_description,
        concourse_url=concourse_url,
    )
    step.on_error = ErrorHandlingStep(
        pipeline_name=pipeline_name,
        status="errored",
        failure_description="Concourse system error",
        step_description=step_description,
        concourse_url=concourse_url,
    )
    step.on_abort = ErrorHandlingStep(
        pipeline_name=pipeline_name,
        status="aborted",
        failure_description="Failed",
        step_description=step_description,
        concourse_url=concourse_url,
    )


class ErrorHandlingStep(TryStep):
    """
    Extends TryStep and sets error handling steps
    """

    def __init__(
        self,
        pipeline_name: str,
        status: str,
        failure_description: str,
        step_description: str,
        concourse_url: str,
        **kwargs,
    ):
        super().__init__(
            try_=(
                DoStep(
                    do=[
                        OcwStudioWebhookStep(
                            pipeline_name=pipeline_name, status=status
                        ),
                        SlackAlertStep(
                            alert_type=status,
                            text=f"{failure_description} - {step_description} : {concourse_url}",
                        ),
                    ]
                )
            ),
            **kwargs,
        )


class GetStepWithErrorHandling(GetStep):
    """
    Extends GetStep and adds error handling
    """

    def __init__(
        self, step_description: str, pipeline_name: str, instance_vars: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            step_description=step_description,
            pipeline_name=pipeline_name,
            instance_vars_query_str=instance_vars,
        )


class PutStepWithErrorHandling(PutStep):
    """
    Extends PutStep and adds error handling
    """

    def __init__(
        self, step_description: str, pipeline_name: str, instance_vars: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            step_description=step_description,
            pipeline_name=pipeline_name,
            instance_vars_query_str=instance_vars,
        )


class TaskStepWithErrorHandling(TaskStep):
    """
    Extends TaskStep and adds error handling
    """

    def __init__(
        self, step_description: str, pipeline_name: str, instance_vars: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            step_description=step_description,
            pipeline_name=pipeline_name,
            instance_vars_query_str=instance_vars,
        )


class SlackAlertStep(TryStep):
    """
    A PutStep to concourse-slack-alert-resource wrapped in a TryStep

    Args:
        alert_type(str): The alert type (started, success, failed, aborted, errored)
        text(str): The text to display inside the alert
    """

    def __init__(self, alert_type: str, text: str, **kwargs):
        super().__init__(
            try_=DoStep(
                do=[
                    PutStep(
                        put=SLACK_ALERT_RESOURCE_IDENTIFIER,
                        timeout="1m",
                        params={"alert_type": alert_type, "text": text},
                    )
                ]
            ),
            **kwargs,
        )


class ClearCdnCacheStep(TaskStep):
    """
    A TaskStep using the curlimages/curl Docker image that sends an
    API request to Fastly to clear the cache for a given URL

    Args:
        name(str): The name to use as the Identifier for the task argument
        fastly_var(str): The name of the var to pull Fastly properties from
        purge_url(str): The URL to purge from the cache
    """

    def __init__(self, name: str, fastly_var: str, purge_url: str, **kwargs):
        curl_args = [
            "-f",
            "-X",
            "POST",
            "-H",
            f"Fastly-Key: '(({fastly_var}.api_token))'",
        ]
        if settings.CONCOURSE_HARD_PURGE:
            curl_args.extend(["-H", "'Fastly-Soft-Purge: 1'"])
        curl_args.append(
            f"https://api.fastly.com/service/(({fastly_var}.service_id))/{purge_url}"
        )
        super().__init__(
            task=Identifier(name),
            timeout="5m",
            attempts=3,
            config=TaskConfig(
                platform="linux",
                image_resource=CURL_REGISTRY_IMAGE,
                run=Command(path="sh", args=curl_args),
            ),
            **kwargs,
        )


class OcwStudioWebhookStep(TryStep):
    """
    A PutStep to the ocw-studio api resource that sets a status on a given pipeline

    Args:
        pipeline_name(str): The name of the pipeline to set the status on
        status: (str): The status to set on the pipeline (failed, errored, succeeded)
    """

    def __init__(self, pipeline_name: str, status: str, **kwargs):
        super().__init__(
            try_=PutStep(
                put=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps({"version": pipeline_name, "status": status})
                },
            ),
            **kwargs,
        )


class OpenDiscussionsWebhookStep(TryStep):
    """
    A PutStep to the open-discussions api resource that refreshes the search index for a given site_url and version

    Args:
        site_url(str): The url path of the site
        pipeline_name(str): The pipeline name to use as the version (draft / live)
    """

    def __init__(self, site_url: str, pipeline_name: str, **kwargs):
        super().__init__(
            try_=PutStep(
                put=OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps(
                        {
                            "webhook_key": settings.OCW_NEXT_SEARCH_WEBHOOK_KEY,
                            "prefix": f"{site_url}/",
                            "version": pipeline_name,
                        }
                    )
                },
            ),
            **kwargs,
        )
