import json

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    DoStep,
    GetStep,
    Identifier,
    PutStep,
    Step,
    TaskConfig,
    TaskStep,
    TryStep,
)

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    CURL_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resources import SlackAlertResource
from main.utils import is_dev


PURGE_HEADER = (
    ""
    if settings.CONCOURSE_HARD_PURGE
    else "\n              - -H\n              - 'Fastly-Soft-Purge: 1'"
)


def add_error_handling(
    step: Step, pipeline_name: str, site_name: str, step_description: str
):
    on_failure_steps = [
        OcwStudioWebhookStep(pipeline_name=pipeline_name, status="failed")
    ]
    on_error_steps = [
        OcwStudioWebhookStep(pipeline_name=pipeline_name, status="errored")
    ]
    on_abort_steps = [
        OcwStudioWebhookStep(pipeline_name=pipeline_name, status="errored")
    ]
    if not is_dev():
        on_failure_steps.append(
            SlackAlertStep(
                alert_type="failed",
                text=f"Failed - {step_description} : {pipeline_name}/{site_name}",
            )
        )
        on_error_steps.append(
            SlackAlertStep(
                alert_type="errored",
                text=f"Concourse system error - {step_description} : {pipeline_name}/{site_name}",
            )
        )
        on_abort_steps.append(
            SlackAlertStep(
                alert_type="errored",
                text=f"Concourse system error - {step_description} : {pipeline_name}/{site_name}",
            )
        )
    step.on_failure = TryStep(try_=DoStep(do=on_failure_steps))
    step.on_error = TryStep(try_=DoStep(do=on_error_steps))
    step.on_abort = TryStep(try_=DoStep(do=on_abort_steps))


class GetStepWithErrorHandling(GetStep):
    def __init__(
        self, pipeline_name: str, site_name: str, step_description: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            pipeline_name=pipeline_name,
            site_name=site_name,
            step_description=step_description,
        )


class PutStepWithErrorHandling(PutStep):
    def __init__(
        self, pipeline_name: str, site_name: str, step_description: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            pipeline_name=pipeline_name,
            site_name=site_name,
            step_description=step_description,
        )


class TaskStepWithErrorHandling(TaskStep):
    def __init__(
        self, pipeline_name: str, site_name: str, step_description: str, **kwargs
    ):
        super().__init__(**kwargs)
        add_error_handling(
            self,
            pipeline_name=pipeline_name,
            site_name=site_name,
            step_description=step_description,
        )


class SlackAlertStep(TryStep):
    def __init__(
        self, slack_alert_resource: SlackAlertResource, alert_type: str, text: str
    ):
        super().__init__(
            try_=DoStep(
                do=[
                    PutStep(
                        put=slack_alert_resource.name,
                        timeout="1m",
                        params={"alert_type": alert_type, "text": text},
                    )
                ]
            )
        )


class ClearCdnCacheStep(TaskStep):
    def __init__(self, name: str, fastly_var: str, purge_url: str):
        super().__init__(
            task=Identifier(name),
            timeout="5m",
            attempts=3,
            config=TaskConfig(
                platform="linux",
                image_resource=CURL_REGISTRY_IMAGE,
                run=Command(
                    path="sh",
                    args=[
                        "-f",
                        "-X",
                        "POST",
                        "-H",
                        f"Fastly-Key: (({fastly_var}.api_token))'{PURGE_HEADER}",
                        f"https://api.fastly.com/service/(({fastly_var}.service_id))/{purge_url}",
                    ],
                ),
            ),
        )


class OcwStudioWebhookStep(TryStep):
    def __init__(self, pipeline_name: str, status: str):
        super().__init__(
            try_=PutStep(
                put=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps({"version": pipeline_name, "status": status})
                },
            )
        )


class OpenDiscussionsWebhookStep(TryStep):
    def __init__(self, site_url: str, pipeline_name: str):
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
            )
        )
