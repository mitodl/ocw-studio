import json
from typing import Optional  # noqa: F401
from urllib.parse import urljoin

from django.conf import settings
from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import (
    AcrossVar,  # noqa: F401
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
    OCW_STUDIO_WEBHOOK_SKIPPED_IDENTIFIER,
    SITE_CONTENT_GIT_IDENTIFIER,
    SLACK_ALERT_RESOURCE_IDENTIFIER,
    get_fastly_identifier,
    get_ocw_catalog_identifier,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    CURL_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    get_fastly_purge_purposes,
)
from content_sync.utils import get_ocw_studio_api_url


def add_error_handling(  # noqa: PLR0913, PLR0917
    step: StepModifierMixin,
    step_description: str,
    pipeline_name: str,
    short_id: str,  # noqa: ARG001
    instance_vars: str,
    build_type: str | None = None,
    theme_slug: str | None = None,
    skip_webhooks: bool = False,  # noqa: FBT001, FBT002
):
    """
    Add error handling steps to any Step-like object

    Args:
        step(StepModifierMixin): The Step-like object that uses StepModifierMixin to add the error handling steps to
        step_description(str): A description of the step at which the failure occurred
        pipeline_name(str): The name of the pipeline to set the status on
        short_id(str): The short_id of the site the status is in reference to
        instance_vars(str): A query string of the instance vars from the pipeline to build a URL with
        build_type(str, optional): The type of build ('online' or 'offline')
        theme_slug(str | None, optional): The theme slug for the build.

    Returns:
        The step with error handling added
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
        build_type=build_type,
        theme_slug=theme_slug,
        skip_webhooks=skip_webhooks,
    )
    step.on_error = ErrorHandlingStep(
        pipeline_name=pipeline_name,
        status="errored",
        failure_description="Concourse system error",
        step_description=step_description,
        concourse_url=concourse_url,
        build_type=build_type,
        theme_slug=theme_slug,
        skip_webhooks=skip_webhooks,
    )
    step.on_abort = ErrorHandlingStep(
        pipeline_name=pipeline_name,
        status="aborted",
        failure_description="Aborted",
        step_description=step_description,
        concourse_url=concourse_url,
        build_type=build_type,
        theme_slug=theme_slug,
        skip_webhooks=skip_webhooks,
    )
    return step


class ErrorHandlingStep(TryStep):
    """
    Extends TryStep and sets error handling steps
    """

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        pipeline_name: str,
        status: str,
        failure_description: str,
        step_description: str,
        concourse_url: str,
        build_type: str | None = None,
        theme_slug: str | None = None,
        skip_webhooks: bool = False,  # noqa: FBT001, FBT002
        **kwargs,
    ):
        super().__init__(
            try_=(
                DoStep(
                    do=[
                        OcwStudioWebhookStep(
                            pipeline_name=pipeline_name,
                            status=status,
                            build_type=build_type,
                            theme_slug=theme_slug,
                            skip=skip_webhooks,
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
        self.model_rebuild()


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
                        no_get=True,
                    )
                ]
            ),
            **kwargs,
        )
        self.model_rebuild()


class ClearCdnCacheStep(PutStep):
    """
    A PutStep to the ol-concourse Fastly resource that purges a site's surrogate key
    from one Fastly distribution.

    The step is labelled with `name` and targets the resource for `purpose`, so the
    step keeps a readable identifier rather than being named after the resource.

    The resource has no internal retry, so `attempts` is kept here. A surrogate key
    purge is idempotent, so retrying is safe.

    Args:
        name(str): The name to use as the Identifier for the step
        purpose(str): The distribution to purge, e.g. "draft", "live" or "learn"
        site_name(str): The surrogate key to purge from the cache
    """

    def __init__(self, name: Identifier, purpose: str, site_name: str, **kwargs):
        params = {
            "mode": "surrogate_key",
            "surrogate_key": site_name,
        }
        if not settings.CONCOURSE_HARD_PURGE:
            params["soft"] = True
        super().__init__(
            put=name,
            resource=get_fastly_identifier(purpose),
            timeout="5m",
            attempts=3,
            params=params,
            inputs=[],
            no_get=True,
            **kwargs,
        )
        self.model_rebuild()


def clear_cdn_cache_steps(
    name: Identifier,
    purpose: str,
    site_name: str,
    **kwargs,
) -> list[ClearCdnCacheStep]:
    """
    Build one purge step per distribution a build for `purpose` must purge.

    A live build also purges the MIT Learn distribution, which serves ocw-course-v3
    content. The first step keeps `name` so the primary purge has a stable identifier;
    any additional purge is suffixed with its purpose.

    Callers that attach an on_success handler should attach it to the last step only,
    so it fires once all purges have succeeded.

    Args:
        name(str): The Identifier to use for the primary purge step
        purpose(str): The distribution being published to, e.g. "draft" or "live"
        site_name(str): The surrogate key to purge from the cache

    Returns:
        list[ClearCdnCacheStep]: One step per distribution, the primary one first
    """
    return [
        ClearCdnCacheStep(
            name=name if index == 0 else Identifier(f"{name}-{item}").root,
            purpose=item,
            site_name=site_name,
            **kwargs,
        )
        for index, item in enumerate(get_fastly_purge_purposes(purpose))
    ]


class OcwStudioWebhookStep(TryStep):
    """
    A PutStep to the ocw-studio api resource that sets a status on a given pipeline.

    Args:
        pipeline_name(str): The name of the pipeline to set the status on
        status: (str): The status to set on the pipeline (failed, errored, succeeded)
        build_type: (str, optional): The type of build ('online' or 'offline')
        is_cdn_cache_step(bool, optional): Whether this step is being called from
                                           a cdn cache purge step
        theme_slug(str | None): The theme slug for the build.
        skip(bool): Whether to skip the webhook with a no-op task.
    """

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        pipeline_name: str,
        status: str,
        build_type: str | None = None,
        is_cdn_cache_step: bool = False,  # noqa: FBT001,FBT002
        theme_slug: str | None = None,
        skip: bool = False,  # noqa: FBT001,FBT002
        **kwargs,
    ):
        theme_slug = theme_slug or ""
        if skip:
            try_step = TaskStep(
                task=OCW_STUDIO_WEBHOOK_SKIPPED_IDENTIFIER,
                config=TaskConfig(
                    platform="linux",
                    image_resource=CURL_REGISTRY_IMAGE,
                    run=Command(path="true"),
                ),
            )
        else:
            webhook_data = {
                "version": pipeline_name,
                "status": status,
                "build_id": "$BUILD_ID",
                "build_type": build_type,
                "is_cdn_cache_step": is_cdn_cache_step,
                "theme_slug": theme_slug,
            }
            try_step = PutStep(
                put=OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER,
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps(webhook_data),
                    "build_metadata": ["body"],
                },
                inputs=[],
                no_get=True,
            )
        super().__init__(try_=try_step, **kwargs)
        self.model_rebuild()


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
        self.model_rebuild()


class OpenCatalogWebhookStep(TryStep):
    """
    A PutStep to an open catalog api resource that refreshes the search index for a given site_url and version

    Args:
        site_url(str): The url path of the site
        pipeline_name(str): The pipeline name to use as the version (draft / live)
    """  # noqa: E501

    def __init__(
        self, site_url: str, pipeline_name: str, open_catalog_url: str, **kwargs
    ):
        super().__init__(
            try_=PutStep(
                put=get_ocw_catalog_identifier(open_catalog_url),
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps(
                        {
                            "webhook_key": settings.OPEN_CATALOG_WEBHOOK_KEY,
                            "prefix": f"{site_url}/",
                            "version": pipeline_name,
                        }
                    )
                },
                inputs=[],
                no_get=True,
            ),
            **kwargs,
        )
        self.model_rebuild()


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
        self.model_rebuild()
