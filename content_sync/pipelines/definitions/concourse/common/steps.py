import json
from urllib.parse import urljoin

from django.conf import settings
from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import (
    AnonymousResource,
    Command,
    DoStep,
    Identifier,
    Output,
    PutStep,
    RegistryImage,
    StepModifierMixin,
    TaskConfig,
    TaskStep,
    TryStep,
)

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_STUDIO_WEBHOOK_CURL_STEP_IDENTIFIER,
    OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
    OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    CURL_REGISTRY_IMAGE,
)
from content_sync.utils import get_ocw_studio_api_url


def add_error_handling(
    step: StepModifierMixin,
    step_description: str,
    pipeline_name: str,
    short_id: str,  # noqa: ARG001
    instance_vars: str,
):
    """
    Add error handling steps to any Step-like object

    Args:
        step(StepModifierMixin): The Step-like object that uses StepModifierMixin to add the error handling steps to
        step_description(str): A description of the step at which the failure occurred
        pipeline_name(str): The name of the pipeline to set the status on
        short_id(str): The short_id of the site the status is in reference to
        instance_vars(str): A query string of the instance vars from the pipeline to build a URL with

    Returns:
        None
    """  # noqa: E501
    step_type = type(step)
    if not issubclass(step_type, StepModifierMixin):
        msg = f"The step object of type {step_type} does not extend StepModifierMixin and therefore cannot have error handling"  # noqa: E501
        raise TypeError(msg)
    for failure_step in [step.on_failure, step.on_error, step.on_abort]:
        if failure_step is not None:
            msg = f"The step {step} already has {failure_step} set"
            raise ValueError(msg)
    concourse_base_url = settings.CONCOURSE_URL
    concourse_team = settings.CONCOURSE_TEAM
    concourse_path = f"/teams/{concourse_team}/pipelines/{pipeline_name}{instance_vars}"
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
        failure_description="Aborted",
        step_description=step_description,
        concourse_url=concourse_url,
    )
    return step


class ErrorHandlingStep(TryStep):
    """
    Extends TryStep and sets error handling steps
    """

    def __init__(  # noqa: PLR0913
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
                            pipeline_name=pipeline_name,
                            status=status,
                        ),
                        SlackAlertStep(
                            alert_type=status,
                            text=f"{failure_description} - {step_description} : {concourse_url}",  # noqa: E501
                        ),
                    ]
                )
            ),
            **kwargs,
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
                        inputs=[],
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
        site_name(str): The site to purge from the cache
    """

    def __init__(self, name: Identifier, fastly_var: str, site_name: str, **kwargs):
        curl_args = [
            "-f",
            "-X",
            "POST",
            "-H",
            f"Fastly-Key: (({fastly_var}.api_token))",
        ]
        if not settings.CONCOURSE_HARD_PURGE:
            curl_args.extend(["-H", "Fastly-Soft-Purge: 1"])
        curl_args.append(
            f"https://api.fastly.com/service/(({fastly_var}.service_id))/purge/{site_name}"
        )
        super().__init__(
            task=name,
            timeout="5m",
            attempts=3,
            config=TaskConfig(
                platform="linux",
                image_resource=CURL_REGISTRY_IMAGE,
                run=Command(path="curl", args=curl_args),
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
                inputs=[],
            ),
            **kwargs,
        )


class OcwStudioWebhookCurlStep(TryStep):
    """
    A TaskStep to POST JSON data to the ocw-studio API for a given site using curl

    Args:
        site_name(str): The name of the site to set the status on
        data(dict): A dict of data to be transformed to JSON and passed to the API
    """

    def __init__(self, site_name: str, data: dict, **kwargs):
        super().__init__(
            try_=TaskStep(
                task=OCW_STUDIO_WEBHOOK_CURL_STEP_IDENTIFIER,
                timeout="1m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=CURL_REGISTRY_IMAGE,
                    run=Command(
                        path="curl",
                        args=[
                            "-f",
                            "-X",
                            "POST",
                            "-H",
                            "Content-Type: application/json",
                            "-H",
                            f"Authorization: Bearer {settings.API_BEARER_TOKEN}",
                            "--data",
                            json.dumps(data),
                            f"{get_ocw_studio_api_url().rstrip('/')}/api/websites/{site_name}/pipeline_status/",
                        ],
                    ),
                ),
            ),
            **kwargs,
        )


class OpenDiscussionsWebhookStep(TryStep):
    """
    A PutStep to the open-discussions api resource that refreshes the search index for a given site_url and version

    Args:
        site_url(str): The url path of the site
        pipeline_name(str): The pipeline name to use as the version (draft / live)
    """  # noqa: E501

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
                inputs=[],
            ),
            **kwargs,
        )


class SiteContentGitTaskStep(TaskStep):
    """
    A TaskStep for fetching the site content git repository

    Args:
        branch(str): The branch of the site content repository to fetch
        short_id(str): The short_id property of the Website
    """

    def __init__(self, branch: str, short_id: str, **kwargs):
        if settings.CONCOURSE_IS_PRIVATE_REPO:
            uri = (
                f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{short_id}.git"
            )
            command = f"""
            echo $GIT_PRIVATE_KEY > ./git.key
            sed -i -E \"s/(-----BEGIN[^-]+-----)(.+)(-----END[^-]+-----)/-----BEGINSSHKEY-----\\2\\-----ENDSSHKEY-----/\" git.key
            sed -i -E \"s/\\s/\\n/g\" git.key
            sed -i -E \"s/SSHKEY/ OPENSSH PRIVATE KEY/g\" git.key
            chmod 400 ./git.key
            GIT_PRIVATE_KEY_FILE=\"-i ./git.key\"
            git -c core.sshCommand=\"ssh $GIT_PRIVATE_KEY_FILE -o StrictHostKeyChecking=no\" clone -b {branch} {uri} ./{SITE_CONTENT_GIT_IDENTIFIER}
            """  # noqa: E501
            params = {"GIT_PRIVATE_KEY": "((git-private-key))"}
        else:
            uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{short_id}.git"
            command = f"git clone -b {branch} {uri} ./{SITE_CONTENT_GIT_IDENTIFIER}"
            params = {}
        super().__init__(
            task=SITE_CONTENT_GIT_IDENTIFIER,
            timeout="40m",
            attempts=3,
            params=params,
            config=TaskConfig(
                platform="linux",
                image_resource=AnonymousResource(
                    type=REGISTRY_IMAGE,
                    source=RegistryImage(repository="alpine/git", tag="latest"),
                ),
                outputs=[Output(name=SITE_CONTENT_GIT_IDENTIFIER)],
                run=Command(
                    path="sh",
                    args=["-exc", command],
                ),
            ),
            **kwargs,
        )
