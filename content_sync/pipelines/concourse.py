"""
Concourse-CI preview/publish pipeline generator
The pylint no-name-in-module is disabled here because of a weird issue
that occurred after adding the OCW_HUGO_THEMES_GIT constant, which
clearly exists but pylint thinks it doesn't
"""
# pylint: disable=no-name-in-module
import json
import logging
import os
from html import unescape
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml
from concoursepy.api import Api
from django.conf import settings
from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import (
    AnonymousResource,
    Command,
    DoStep,
    GetStep,
    Identifier,
    Input,
    Job,
    Output,
    Pipeline,
    PutStep,
    RegistryImage,
    Resource,
    ResourceType,
    Step,
    StepModifierMixin,
    TaskConfig,
    TaskStep,
    TryStep,
)
from ol_concourse.lib.resource_types import slack_notification_resource
from requests import HTTPError

from content_sync.constants import (
    DEV_ENDPOINT_URL,
    TARGET_OFFLINE,
    TARGET_ONLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.decorators import retry_on_failure
from content_sync.pipelines.base import (
    BaseGeneralPipeline,
    BaseMassBuildSitesPipeline,
    BasePipelineApi,
    BaseSitePipeline,
    BaseThemeAssetsPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from content_sync.utils import (
    check_mandatory_settings,
    get_hugo_arg_string,
    get_template_vars,
    get_theme_branch,
    strip_dev_lines,
    strip_non_dev_lines,
    strip_offline_lines,
    strip_online_lines,
)
from main.constants import PRODUCTION_NAMES
from main.utils import is_dev
from websites.constants import OCW_HUGO_THEMES_GIT, STARTER_SOURCE_GITHUB
from websites.models import Website


log = logging.getLogger(__name__)

MANDATORY_CONCOURSE_SETTINGS = [
    "CONCOURSE_URL",
    "CONCOURSE_USERNAME",
    "CONCOURSE_PASSWORD",
]


PURGE_HEADER = (
    ""
    if settings.CONCOURSE_HARD_PURGE
    else "\n              - -H\n              - 'Fastly-Soft-Purge: 1'"
)

# Identifiers

OCW_STUDIO_WEBHOOK_IDENTIFIER = Identifier("ocw-studio-webhook")

# Resource Types

HTTP_RESOURCE_TYPE = ResourceType(
    name=Identifier("http-resource"),
    type=REGISTRY_IMAGE,
    source={"repository": "jgriff/http-resource", "tag": "latest"},
)

KEYVAL_RESOURCE_TYPE = ResourceType(
    name=Identifier("keyval"),
    type=REGISTRY_IMAGE,
    source={"repository": "ghcr.io/cludden/concourse-keyval-resource", "tag": "latest"},
)

S3_IAM_RESOURCE_TYPE = ResourceType(
    name=Identifier("s3-resource-iam"),
    type=REGISTRY_IMAGE,
    source={"repository": "governmentpaas/s3-resource", "tag": "latest"},
)

# Image Resources

OCW_COURSE_PUBLISHER_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE,
    source=RegistryImage(repository="mitodl/ocw-course-publisher", tag="0.6"),
)

AWS_CLI_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="amazon/aws-cli", tag="latest")
)

CURL_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="curlimages/curl")
)

# Static Resources

SLACK_ALERT_RESOURCE = Resource(
    name=Identifier("slack-alert"),
    type=slack_notification_resource.__name__,
    check_every="never",
    source={"url": "((slack-url))", "disabled": "false"},
)

OPEN_DISCUSSIONS_RESOURCE = Resource(
    name=Identifier("open-discussions-webhook"),
    type=HTTP_RESOURCE_TYPE.name,
    check_every="never",
    source={
        "url": f"{settings.OPEN_DISCUSSIONS_URL}/api/v0/ocw_next_webhook/",
        "method": "POST",
        "out_only": True,
        "headers": {
            "Content-Type": "application/json",
        },
    },
)

# Resource Generators


class GitResource(Resource):
    def __init__(self, name: Identifier, uri: str, branch: str):
        super().__init__(
            name=name,
            type="git",
            source={"uri": uri, "branch": branch},
        )


class OcwStudioWebhookResource(Resource):
    def __init__(self, ocw_studio_url: str, site_name: str, api_token: str):
        super().__init__(
            name=OCW_STUDIO_WEBHOOK_IDENTIFIER,
            type=HTTP_RESOURCE_TYPE.name,
            check_every="never",
            source={
                "url": f"{ocw_studio_url}/api/websites/{site_name}/pipeline_status/",
                "method": "POST",
                "out_only": True,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}",
                },
            },
        )


# Step Generators


def add_error_handling(
    step: Step, pipeline_name: str, site_name: str, step_description: str
):
    step.on_failure = (
        TryStep(
            try_=DoStep(
                do=[
                    OcwStudioWebhookStep(pipeline_name=pipeline_name, status="failed"),
                    SlackAlertStep(
                        alert_type="failed",
                        text=f"Failed - {step_description} : {pipeline_name}/{site_name}",
                    ),
                ]
            )
        ),
    )
    step.on_error = (
        TryStep(
            try_=DoStep(
                do=[
                    OcwStudioWebhookStep(pipeline_name=pipeline_name, status="errored"),
                    SlackAlertStep(
                        alert_type="errored",
                        text=f"Concourse system error - {step_description} : {pipeline_name}/{site_name}",
                    ),
                ]
            )
        ),
    )
    step.on_abort = TryStep(
        try_=DoStep(
            do=[
                OcwStudioWebhookStep(pipeline_name=pipeline_name, status="aborted"),
                SlackAlertStep(
                    alert_type="aborted",
                    text=f"User aborted - {step_description} : {pipeline_name}/{site_name}",
                ),
            ]
        )
    )


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
    def __init__(self, alert_type: str, text: str):
        super().__init__(
            try_=DoStep(
                do=[
                    PutStep(
                        put=SLACK_ALERT_RESOURCE.name,
                        timeout="1m",
                        params={"alert_type": alert_type, "text": text},
                    )
                ]
            )
        )


class ClearCdnCacheStep(TaskStep):
    def __init__(self, fastly_var: str):
        super().__init__(
            task=Identifier("clear-cdn-cache-draft"),
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
                        f"https://api.fastly.com/service/(({fastly_var}.service_id))/purge/ocw-hugo-themes",
                    ],
                ),
            ),
        )


class OcwStudioWebhookStep(TryStep):
    def __init__(self, pipeline_name: str, status: str):
        super().__init__(
            try_=PutStep(
                put=OCW_STUDIO_WEBHOOK_IDENTIFIER,
                timeout="1m",
                attempts=3,
                params={
                    "text": json.dumps({"version": pipeline_name, "status": status})
                },
            )
        )


class PipelineApi(Api, BasePipelineApi):
    """
    Customized pipeline_name of concoursepy.api.Api that allows for getting/setting headers
    """

    def __init__(self, url=None, username=None, password=None, token=None):
        """Initialize the API"""
        super().__init__(
            url or settings.CONCOURSE_URL,
            username=username or settings.CONCOURSE_USERNAME,
            password=password or settings.CONCOURSE_PASSWORD,
            token=token or settings.CONCOURSE_TEAM,
        )

    @retry_on_failure
    def auth(self):
        """Same as the base class but with retries and support for concourse 7.7"""
        if self.has_username_and_passwd:
            self.ATC_AUTH = None
            session = self._set_new_session()
            # Get initial sky/login response
            r = session.get(urljoin(self.url, "/sky/login"))
            if r.status_code == 200:
                # Get second sky/login response based on the url found in the first response
                r = session.get(
                    unescape(urljoin(self.url, self._get_login_post_path(r.text)))
                )
                # Post to the final url to authenticate
                post_path = unescape(self._get_login_post_path(r.text))
                r = session.post(
                    urljoin(self.url, post_path),
                    data={"login": self.username, "password": self.password},
                )
                try:
                    r.raise_for_status()
                except HTTPError:
                    self._close_session()
                    raise
                else:
                    # This case does not raise any HTTPError, the return code is 200
                    if "invalid username and password" in r.text:
                        raise ValueError("Invalid username and password")
                    if r.status_code == requests.codes.ok:
                        self.ATC_AUTH = self._get_skymarshal_auth()
                    else:
                        self._close_session()
        if self.ATC_AUTH:
            return True
        return False

    @retry_on_failure
    def get_with_headers(  # pylint:disable=too-many-branches
        self, path: str, stream: bool = False, iterator: bool = False
    ) -> Tuple[Dict, Dict]:
        """Customized base get method, returning response data and headers"""
        url = self._make_api_url(path)
        r = self.requests.get(url, headers=self.headers, stream=stream)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.get(url, headers=self.headers, stream=stream)
        if r.status_code == requests.codes.ok:
            if stream:
                if iterator:
                    response_data = self.iter_sse_stream(r)
                else:
                    response_data = list(self.iter_sse_stream(r))
            else:
                response_data = json.loads(r.text)
            return response_data, r.headers
        else:
            r.raise_for_status()

    @retry_on_failure
    def put_with_headers(
        self, path: str, data: Dict = None, headers: Dict = None
    ) -> bool:
        """
        Allow additional headers to be sent with a put request
        """
        url = self._make_api_url(path)
        request_headers = self.headers
        request_headers.update(headers or {})
        kwargs = {"headers": request_headers}
        if data is not None:
            kwargs["data"] = data
        r = self.requests.put(url, **kwargs)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.put(url, **kwargs)
        if r.status_code == requests.codes.ok:
            return True
        else:
            r.raise_for_status()
        return False

    @retry_on_failure
    def post(self, path, data=None):
        """Same as base post method but with a retry"""
        return super().post(path, data)

    @retry_on_failure
    def put(self, path, data=None):
        """Same as base put method but with a retry"""
        return super().put(path, data)

    @retry_on_failure
    def delete(self, path, data=None):
        """Make a delete request"""
        url = self._make_api_url(path)
        kwargs = {"headers": self.headers}
        if data is not None:
            kwargs["data"] = data
        r = self.requests.delete(url, **kwargs)
        if not self._is_response_ok(r) and self.has_username_and_passwd:
            self.auth()
            r = self.requests.delete(url, **kwargs)
        if r.status_code == requests.codes.ok:
            return True
        else:
            r.raise_for_status()
        return False

    def get_pipelines(self, names: List[str] = None):
        """Retrieve a list of concourse pipelines, filtered by team and optionally name"""
        pipelines = super().list_pipelines(settings.CONCOURSE_TEAM)
        if names:
            pipelines = [
                pipeline for pipeline in pipelines if pipeline["name"] in names
            ]
        return pipelines

    def delete_pipelines(self, names: List[str] = None):
        """Delete all pipelines matching filters"""
        pipeline_list = self.get_pipelines(names)
        for item in pipeline_list:
            pipeline = GeneralPipeline(api=self)
            instance_vars = item.get("instance_vars")
            if instance_vars:
                pipeline.set_instance_vars(instance_vars)
            pipeline.delete_pipeline(item["name"])


class GeneralPipeline(BaseGeneralPipeline):
    """Base class for a Concourse pipeline"""

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS
    PIPELINE_NAME = None

    def __init__(
        self, *args, api: Optional[object] = None, **kwargs
    ):  # pylint:disable=unused-argument
        """Initialize the pipeline API instance"""
        if self.MANDATORY_SETTINGS:
            check_mandatory_settings(self.MANDATORY_SETTINGS)
        self.instance_vars = ""
        self.api = api or self.get_api()

    @staticmethod
    def get_api():
        """Get a Concourse API instance"""
        return PipelineApi()

    def get_pipeline_definition(
        self, pipeline_file: str, offline: Optional[bool] = None
    ):
        """Get the pipeline definition as a string, processing for environment"""
        with open(
            os.path.join(os.path.dirname(__file__), pipeline_file)
        ) as pipeline_config_file:
            pipeline_config = pipeline_config_file.read()
            pipeline_config = (
                strip_non_dev_lines(pipeline_config)
                if is_dev()
                else strip_dev_lines(pipeline_config)
            )
            pipeline_config = (
                strip_online_lines(pipeline_config)
                if offline
                else strip_offline_lines(pipeline_config)
            )
            return pipeline_config

    def set_instance_vars(self, instance_vars: Dict):
        """Set the instance vars for the pipeline"""
        self.instance_vars = f"?vars={quote(json.dumps(instance_vars))}"

    def _make_pipeline_url(self, pipeline_name: str):
        """Make URL for getting/destroying a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}{self.instance_vars}"

    def _make_builds_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching builds information"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}/builds{self.instance_vars}"

    def _make_pipeline_config_url(self, pipeline_name: str):
        """Make URL for fetching pipeline info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/config{self.instance_vars}"

    def _make_job_url(self, pipeline_name: str, job_name: str):
        """Make URL for fetching job info"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/jobs/{job_name}{self.instance_vars}"

    def _make_pipeline_pause_url(self, pipeline_name: str):
        """Make URL for pausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/pause{self.instance_vars}"

    def _make_pipeline_unpause_url(self, pipeline_name: str):
        """Make URL for unpausing a pipeline"""
        return f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{pipeline_name}/unpause{self.instance_vars}"

    def trigger_pipeline_build(self, pipeline_name: str) -> int:
        """Trigger a pipeline build"""
        pipeline_info = self.api.get(self._make_pipeline_config_url(pipeline_name))
        job_name = pipeline_info["config"]["jobs"][0]["name"]
        return self.api.post(self._make_builds_url(pipeline_name, job_name))["id"]

    def pause_pipeline(self, pipeline_name: str):
        """Pause the pipeline"""
        self.api.put(self._make_pipeline_pause_url(pipeline_name))

    def unpause_pipeline(self, pipeline_name: str):
        """Unpause the pipeline"""
        self.api.put(self._make_pipeline_unpause_url(pipeline_name))

    def delete_pipeline(self, pipeline_name: str):
        """Delete a pipeline"""
        self.api.delete(self._make_pipeline_url(pipeline_name))

    def get_build_status(self, build_id: int):
        """Retrieve the status of the build"""
        return self.api.get_build(build_id)["status"]

    def abort_build(self, build_id: int):
        """Abort a build"""
        return self.api.abort_build(build_id)

    def unpause(self):
        """Use self.PIPELINE_NAME as input to the unpause_pipeline function"""
        if self.PIPELINE_NAME:
            self.unpause_pipeline(self.PIPELINE_NAME)
        else:
            raise ValueError("No default name specified for this pipeline")

    def trigger(self) -> int:
        """Use self.PIPELINE_NAME as input to the trigger_pipeline_build function"""
        if self.PIPELINE_NAME:
            return self.trigger_pipeline_build(self.PIPELINE_NAME)
        else:
            raise ValueError("No default name specified for this pipeline")

    def upsert_config(self, config_str: str, pipeline_name: str):
        """Upsert the configuration for a pipeline"""
        config = json.dumps(yaml.load(config_str, Loader=yaml.SafeLoader))
        log.debug(config)
        # Try to get the pipeline_name of the pipeline if it already exists, because it will be
        # necessary to update an existing pipeline.
        url_path = self._make_pipeline_config_url(pipeline_name)
        try:
            _, headers = self.api.get_with_headers(url_path)
            version_headers = {
                "X-Concourse-Config-Version": headers["X-Concourse-Config-Version"]
            }
        except HTTPError:
            version_headers = None
        self.api.put_with_headers(url_path, data=config, headers=version_headers)

    def upsert_pipeline(self):
        """Placeholder for upsert_pipeline"""
        raise NotImplementedError("Choose a more specific pipeline class")


class ThemeAssetsPipeline(GeneralPipeline, BaseThemeAssetsPipeline):
    """
    Concourse-CI pipeline for publishing theme assets
    """

    PIPELINE_NAME = BaseThemeAssetsPipeline.PIPELINE_NAME
    BRANCH = settings.GITHUB_WEBHOOK_BRANCH

    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
        "GITHUB_WEBHOOK_BRANCH",
        "SEARCH_API_URL",
    ]

    def __init__(
        self, themes_branch: Optional[str] = None, api: Optional[PipelineApi] = None
    ):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.BRANCH = themes_branch or get_theme_branch()
        self.set_instance_vars({"branch": self.BRANCH})

    def upsert_pipeline(self):
        """Upsert the theme assets pipeline"""
        template_vars = get_template_vars()

        ocw_hugo_themes_resource = GitResource(
            name="ocw-hugo-themes", uri=OCW_HUGO_THEMES_GIT, branch=self.BRANCH
        )
        cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""
        resource_types = []
        resources = [ocw_hugo_themes_resource]
        tasks = [
            GetStep(get=ocw_hugo_themes_resource.name, trigger=(not is_dev())),
            TaskStep(
                task=Identifier("build-ocw-hugo-themes"),
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[Input(name=ocw_hugo_themes_resource.name)],
                    outputs=[Output(name=ocw_hugo_themes_resource.name)],
                    params={
                        "SEARCH_API_URL": settings.SEARCH_API_URL,
                        "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
                        "SENTRY_ENV": settings.ENVIRONMENT or "",
                    },
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            """
                            cd ocw-hugo-themes
                            yarn install --immutable
                            npm run build:webpack
                            npm run build:githash
                            """,
                        ],
                    ),
                ),
            ),
            TaskStep(
                task=Identifier("copy-s3-buckets"),
                timeout="20m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    inputs=[Input(name=ocw_hugo_themes_resource.name)],
                    params=(
                        {}
                        if not is_dev()
                        else {
                            "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID or "",
                            "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY
                            or "",
                        }
                    ),
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            aws s3{cli_endpoint_url} cp ocw-hugo-themes/base-theme/dist s3://{template_vars["preview_bucket_name"]} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{cli_endpoint_url} cp ocw-hugo-themes/base-theme/dist s3://{template_vars["publish_bucket_name"]} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{cli_endpoint_url} cp ocw-hugo-themes/base-theme/static s3://{template_vars["preview_bucket_name"]} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{cli_endpoint_url} cp ocw-hugo-themes/base-theme/static s3://{template_vars["publish_bucket_name"]} --recursive --metadata site-id=ocw-hugo-themes
                            aws s3{cli_endpoint_url} cp ocw-hugo-themes/base-theme/data/webpack.json s3://{template_vars["artifacts_bucket_name"]}/ocw-hugo-themes/{self.BRANCH}/webpack.json --metadata site-id=ocw-hugo-themes
                            """,
                        ],
                    ),
                ),
            ),
        ]
        job = Job(name="build-theme-assets", serial=True)
        if not is_dev():
            resource_types.append(slack_notification_resource)
            resources.append(SLACK_ALERT_RESOURCE)
            tasks.append(ClearCdnCacheStep(fastly_var="fastly_draft"))
            tasks.append(ClearCdnCacheStep(fastly_var="fastly_live"))
            job.on_failure = SlackAlertStep(
                alert_type="failed",
                text=f"""
                Failed to build theme assets.

                Append `{self.instance_vars}` to the url below for more details.
                """,
            )
            job.on_abort = SlackAlertStep(
                alert_type="aborted",
                text=f"""
                User aborted while building theme assets.

                Append `{self.instance_vars}` to the url below for more details.
                """,
            )

        job.plan = tasks
        pipeline = Pipeline(
            resource_types=resource_types, resources=resources, jobs=[job]
        )
        config_str = pipeline.json(indent=2)
        self.upsert_config(config_str, self.PIPELINE_NAME)


class SitePipeline(BaseSitePipeline, GeneralPipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend, for individual sites
    """

    BRANCH = settings.GITHUB_WEBHOOK_BRANCH
    MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
        "AWS_OFFLINE_PREVIEW_BUCKET_NAME",
        "AWS_OFFLINE_PUBLISH_BUCKET_NAME",
        "AWS_STORAGE_BUCKET_NAME",
        "GIT_BRANCH_PREVIEW",
        "GIT_BRANCH_RELEASE",
        "GIT_DOMAIN",
        "GIT_ORGANIZATION",
        "GITHUB_WEBHOOK_BRANCH",
        "OCW_GTM_ACCOUNT_ID",
    ]

    def __init__(
        self,
        website: Website,
        hugo_args: Optional[str] = None,
        api: Optional[PipelineApi] = None,
    ):
        """Initialize the pipeline API instance"""
        super().__init__(api=api)
        self.WEBSITE = website
        self.BRANCH = get_theme_branch()
        self.HUGO_ARGS = hugo_args
        self.set_instance_vars({"site": self.WEBSITE.name})

    def upsert_pipeline(self):  # pylint:disable=too-many-locals,too-many-statements
        """
        Create or update a concourse pipeline for the given Website
        """
        ocw_hugo_themes_branch = self.BRANCH
        ocw_hugo_projects_branch = (
            (settings.OCW_HUGO_PROJECTS_BRANCH or self.BRANCH)
            if is_dev()
            else self.BRANCH
        )

        starter = self.WEBSITE.starter
        if starter.source != STARTER_SOURCE_GITHUB:
            # This pipeline only handles sites with github-based starters
            return
        starter_path_url = urlparse(starter.path)
        if not starter_path_url.netloc:
            # Invalid github url, so skip
            return

        if self.WEBSITE.name == settings.ROOT_WEBSITE_NAME:
            base_url = ""
            static_resources_subdirectory = f"/{self.WEBSITE.get_url_path()}/"
            theme_created_trigger = "true"
            theme_deployed_trigger = "false"
        else:
            base_url = self.WEBSITE.get_url_path()
            static_resources_subdirectory = "/"
            theme_created_trigger = "false"
            theme_deployed_trigger = "true"
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
        )
        purge_header = (
            ""
            if settings.CONCOURSE_HARD_PURGE
            else "\n              - -H\n              - 'Fastly-Soft-Purge: 1'"
        )
        for branch_vars in [
            {
                "branch": settings.GIT_BRANCH_PREVIEW,
                "pipeline_name": VERSION_DRAFT,
                "static_api_url": settings.STATIC_API_BASE_URL
                or settings.OCW_STUDIO_DRAFT_URL
                if is_dev()
                else settings.OCW_STUDIO_DRAFT_URL,
            },
            {
                "branch": settings.GIT_BRANCH_RELEASE,
                "pipeline_name": VERSION_LIVE,
                "static_api_url": settings.STATIC_API_BASE_URL
                or settings.OCW_STUDIO_LIVE_URL
                if is_dev()
                else settings.OCW_STUDIO_LIVE_URL,
            },
        ]:
            branch_vars.update(get_template_vars())
            branch = branch_vars["branch"]
            pipeline_name = branch_vars["pipeline_name"]
            static_api_url = branch_vars["static_api_url"]
            storage_bucket_name = branch_vars["storage_bucket_name"]
            artifacts_bucket = branch_vars["artifacts_bucket_name"]
            if branch == settings.GIT_BRANCH_PREVIEW:
                web_bucket = branch_vars["preview_bucket_name"]
                offline_bucket = branch_vars["offline_preview_bucket_name"]
                resource_base_url = branch_vars["resource_base_url_draft"]
            elif branch == settings.GIT_BRANCH_RELEASE:
                web_bucket = branch_vars["publish_bucket_name"]
                offline_bucket = branch_vars["offline_publish_bucket_name"]
                resource_base_url = branch_vars["resource_base_url_live"]
            if (
                branch == settings.GIT_BRANCH_PREVIEW
                or settings.ENV_NAME not in PRODUCTION_NAMES
            ):
                noindex = "true"
            else:
                noindex = "false"
            if settings.CONCOURSE_IS_PRIVATE_REPO:
                markdown_uri = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{self.WEBSITE.short_id}.git"
                private_key_var = "\n      private_key: ((git-private-key))"
            else:
                markdown_uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{self.WEBSITE.short_id}.git"
                private_key_var = ""
            starter_slug = self.WEBSITE.starter.slug
            base_hugo_args = {"--themesDir": "../ocw-hugo-themes/"}
            base_online_args = base_hugo_args.copy()
            base_online_args.update(
                {
                    "--config": f"../ocw-hugo-projects/{starter_slug}/config.yaml",
                    "--baseURL": f"/{base_url}",
                    "--destination": "output-online",
                }
            )
            base_offline_args = base_hugo_args.copy()
            base_offline_args.update(
                {
                    "--config": f"../ocw-hugo-projects/{starter_slug}/config-offline.yaml",
                    "--baseURL": "/",
                    "--destination": "output-offline",
                }
            )
            hugo_args_online = get_hugo_arg_string(
                TARGET_ONLINE,
                pipeline_name,
                base_online_args,
                self.HUGO_ARGS,
            )
            hugo_args_offline = get_hugo_arg_string(
                TARGET_OFFLINE,
                pipeline_name,
                base_offline_args,
                self.HUGO_ARGS,
            )
            cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""

            # Define resource types list
            resource_types = [
                HTTP_RESOURCE_TYPE,
                KEYVAL_RESOURCE_TYPE,
                S3_IAM_RESOURCE_TYPE,
            ]
            if not is_dev():
                resource_types.append(slack_notification_resource)

            # Define resources
            webpack_json_resource = Resource(
                name=Identifier("webpack-json"),
                type=S3_IAM_RESOURCE_TYPE.name,
                check_every="never",
                source={
                    "bucket": (artifacts_bucket or ""),
                    "versioned_file": f"ocw-hugo-themes/{ocw_hugo_themes_branch}/webpack.json",
                },
            )
            if is_dev():
                webpack_json_resource.source.update(
                    {
                        "endpoint": DEV_ENDPOINT_URL,
                        "access_key_id": (settings.AWS_ACCESS_KEY_ID or ""),
                        "secret_access_key": (settings.AWS_SECRET_ACCESS_KEY or ""),
                    }
                )
            offline_build_gate_resource = Resource(
                name=Identifier("offline-build-gate"),
                type=KEYVAL_RESOURCE_TYPE.name,
                check_every="never",
            )
            course_markdown_resource = Resource(
                name=Identifier("course-markdown"),
                type="git",
                check_every="never",
                source={"uri": f"{markdown_uri}{private_key_var}", "branch": branch},
            )
            ocw_hugo_themes_resource = GitResource(
                name=Identifier("ocw-hugo-themes"),
                uri=OCW_HUGO_THEMES_GIT,
                branch=ocw_hugo_projects_branch,
            )
            ocw_hugo_projects_resource = GitResource(
                name=Identifier("ocw-hugo-projects"),
                uri=hugo_projects_url,
                branch=ocw_hugo_projects_branch,
            )
            ocw_studio_webhook_resource = OcwStudioWebhookResource(
                ocw_studio_url=(branch_vars["ocw_studio_url"] or ""),
                site_name=self.WEBSITE.name,
                api_token=settings.API_BEARER_TOKEN or "",
            )
            # Define resources list
            resources = [
                webpack_json_resource,
                offline_build_gate_resource,
                course_markdown_resource,
                ocw_hugo_themes_resource,
                ocw_hugo_projects_resource,
                ocw_studio_webhook_resource,
            ]
            if not is_dev():
                resources.append(OPEN_DISCUSSIONS_RESOURCE)
                resources.append(SLACK_ALERT_RESOURCE)

            # Define online build job tasks
            ocw_studio_webhook_started_step = OcwStudioWebhookStep(
                pipeline_name=pipeline_name, status="started"
            )
            webpack_json_get_step = GetStepWithErrorHandling(
                get=webpack_json_resource.name,
                trigger=False,
                timeout="5m",
                attempts=3,
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="webpack-json get step",
            )
            ocw_hugo_themes_get_step = GetStepWithErrorHandling(
                get=ocw_hugo_themes_resource.name,
                trigger=False,
                timeout="5m",
                attempts=3,
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="ocw-hugo-themes get step",
            )
            ocw_hugo_projects_get_step = GetStepWithErrorHandling(
                get=ocw_hugo_projects_resource.name,
                trigger=False,
                timeout="5m",
                attempts=3,
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="ocw-hugo-projects get step",
            )
            course_markdown_get_step = GetStepWithErrorHandling(
                get=course_markdown_resource.name,
                trigger=False,
                timeout="5m",
                attempts=3,
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="course-markdown get step",
            )
            static_resources_identifier = Identifier("static-resources")
            static_resources_step = TaskStepWithErrorHandling(
                timeout="40m",
                attempts=3,
                params={},
                config=TaskConfig(
                    platform="linux",
                    image_resource=AWS_CLI_REGISTRY_IMAGE,
                    outputs=[Output(name=static_resources_identifier)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f"aws s3{cli_endpoint_url} sync s3://{(storage_bucket_name or '')}/{self.WEBSITE.s3_path} ./static-resources",
                        ],
                    ),
                ),
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="static-resources s3 sync to container",
            )
            if is_dev():
                static_resources_step.params["AWS_ACCESS_KEY_ID"] = (
                    settings.AWS_ACCESS_KEY_ID or ""
                )
                static_resources_step.params["AWS_SECRET_ACCESS_KEY"] = (
                    settings.AWS_SECRET_ACCESS_KEY or ""
                )
            build_course_online_step = TaskStepWithErrorHandling(
                timeout="20m",
                attempts=3,
                params={
                    "API_BEARER_TOKEN": settings.API_BEARER_TOKEN or "",
                    "GTM_ACCOUNT_ID": settings.OCW_GTM_ACCOUNT_ID,
                    "OCW_STUDIO_BASE_URL": branch_vars["ocw_studio_url"] or "",
                    "STATIC_API_BASE_URL": static_api_url,
                    "OCW_IMPORT_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "OCW_COURSE_STARTER_SLUG": settings.OCW_COURSE_STARTER_SLUG,
                    "SITEMAP_DOMAIN": settings.SITEMAP_DOMAIN,
                    "SENTRY_DSN": settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
                    "NOINDEX": noindex,
                },
                config=TaskConfig(
                    platform="linux",
                    image_resource=OCW_COURSE_PUBLISHER_REGISTRY_IMAGE,
                    inputs=[
                        Input(name=ocw_hugo_themes_resource.name),
                        Input(name=ocw_hugo_projects_resource.name),
                        Input(name=course_markdown_resource.name),
                        Input(name=static_resources_identifier),
                        Input(name=webpack_json_resource.name),
                    ],
                    outputs=[
                        Output(name=course_markdown_resource.name),
                        Output(name=ocw_hugo_themes_resource.name),
                    ],
                    run=Command(
                        dir="course-markdown",
                        path="sh",
                        args=[
                            "-exc",
                            f"""
                            cp ../webpack-json/webpack.json ../ocw-hugo-themes/base-theme/data
                            hugo {hugo_args_online}
                            cp -r -n ../static-resources/. ./output-online{static_resources_subdirectory}
                            rm -rf ./output-online{static_resources_subdirectory}*.mp4
                            """,
                        ],
                    ),
                ),
                pipeline_name=pipeline_name,
                site_name=self.WEBSITE.name,
                step_description="build-course-online task step",
            )
            if is_dev():
                build_course_online_step.params["RESOURCE_BASE_URL"] = (
                    resource_base_url or ""
                )
                build_course_online_step.params["AWS_ACCESS_KEY_ID"] = (
                    settings.AWS_ACCESS_KEY_ID or ""
                )
                build_course_online_step.params["AWS_SECRET_ACCESS_KEY"] = (
                    settings.AWS_SECRET_ACCESS_KEY or ""
                )

            online_tasks = [
                ocw_studio_webhook_started_step,
                webpack_json_get_step,
                ocw_hugo_themes_get_step,
                ocw_hugo_projects_get_step,
                course_markdown_get_step,
                static_resources_step,
                build_course_online_step,
            ]
            online_job = Job(
                name=Identifier("build-online-ocw-site"), serial=True, plan=online_tasks
            )
            pipeline = Pipeline(
                resource_types=resource_types, resources=resources, jobs=[online_job]
            )
            config_str = pipeline.json(indent=2)
            log.info(config_str)

            # config_str = (
            #     self.get_pipeline_definition("definitions/concourse/site-pipeline.yml")
            #     .replace("((hugo-args-online))", hugo_args_online)
            #     .replace("((hugo-args-offline))", hugo_args_offline)
            #     .replace("((markdown-uri))", markdown_uri)
            #     .replace("((git-private-key-var))", private_key_var)
            #     .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
            #     .replace("((artifacts-bucket))", artifacts_bucket or "")
            #     .replace("((web-bucket))", web_bucket or "")
            #     .replace("((offline-bucket))", offline_bucket or "")
            #     .replace("((ocw-hugo-themes-branch))", ocw_hugo_themes_branch)
            #     .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
            #     .replace("((ocw-hugo-projects-branch))", ocw_hugo_projects_branch)
            #     .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
            #     .replace("((ocw-studio-url))", branch_vars["ocw_studio_url"] or "")
            #     .replace("((static-api-base-url))", static_api_url)
            #     .replace(
            #         "((ocw-import-starter-slug))", settings.OCW_COURSE_STARTER_SLUG
            #     )
            #     .replace(
            #         "((ocw-course-starter-slug))", settings.OCW_COURSE_STARTER_SLUG
            #     )
            #     .replace("((ocw-studio-bucket))", storage_bucket_name or "")
            #     .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
            #     .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
            #     .replace("((short-id))", self.WEBSITE.short_id)
            #     .replace("((ocw-site-repo-branch))", branch)
            #     .replace("((config-slug))", self.WEBSITE.starter.slug)
            #     .replace("((s3-path))", self.WEBSITE.s3_path)
            #     .replace("((base-url))", base_url)
            #     .replace("((site-url))", self.WEBSITE.get_url_path())
            #     .replace("((site-name))", self.WEBSITE.name)
            #     .replace("((purge-url))", f"purge/{self.WEBSITE.name}")
            #     .replace("((purge_header))", purge_header)
            #     .replace("((pipeline_name))", pipeline_name)
            #     .replace("((api-token))", settings.API_BEARER_TOKEN or "")
            #     .replace("((theme-deployed-trigger))", theme_deployed_trigger)
            #     .replace("((theme-created-trigger))", theme_created_trigger)
            #     .replace("((sitemap-domain))", settings.SITEMAP_DOMAIN)
            #     .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            #     .replace(
            #         "((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or ""
            #     )
            #     .replace("((endpoint-url))", DEV_ENDPOINT_URL)
            #     .replace(
            #         "((cli-endpoint-url))",
            #         f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            #     )
            #     .replace("((resource-base-url))", resource_base_url or "")
            #     .replace(
            #         "((static-resources-subdirectory))", static_resources_subdirectory
            #     )
            #     .replace(
            #         "((ocw-hugo-themes-sentry-dsn))",
            #         settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
            #     )
            #     .replace(
            #         "((delete))",
            #         ""
            #         if self.WEBSITE.name == settings.ROOT_WEBSITE_NAME
            #         else " --delete",
            #     )
            #     .replace(
            #         "((is-root-website))",
            #         str(self.WEBSITE.name == settings.ROOT_WEBSITE_NAME),
            #     )
            #     .replace("((noindex))", noindex)
            # )
            # self.upsert_config(config_str, pipeline_name)


class MassBuildSitesPipeline(
    BaseMassBuildSitesPipeline, GeneralPipeline
):  # pylint: disable=too-many-instance-attributes
    """Specialized concourse pipeline for mass building multiple sites"""

    PIPELINE_NAME = BaseMassBuildSitesPipeline.PIPELINE_NAME

    def __init__(  # pylint: disable=too-many-arguments
        self,
        version,
        api: Optional[PipelineApi] = None,
        prefix: Optional[str] = None,
        themes_branch: Optional[str] = None,
        projects_branch: Optional[str] = None,
        starter: Optional[str] = None,
        offline: Optional[bool] = None,
        hugo_args: Optional[str] = None,
    ):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
            "AWS_PREVIEW_BUCKET_NAME",
            "AWS_PUBLISH_BUCKET_NAME",
            "AWS_OFFLINE_PREVIEW_BUCKET_NAME",
            "AWS_OFFLINE_PUBLISH_BUCKET_NAME",
            "AWS_STORAGE_BUCKET_NAME",
            "GIT_BRANCH_PREVIEW",
            "GIT_BRANCH_RELEASE",
            "GIT_DOMAIN",
            "GIT_ORGANIZATION",
            "GITHUB_WEBHOOK_BRANCH",
            "OCW_GTM_ACCOUNT_ID",
            "SEARCH_API_URL",
        ]
        super().__init__(api=api)
        self.pipeline_name = "mass_build_sites"
        self.VERSION = version
        if prefix:
            self.PREFIX = prefix[1:] if prefix.startswith("/") else prefix
        else:
            self.PREFIX = ""
        self.THEMES_BRANCH = themes_branch if themes_branch else get_theme_branch()
        self.PROJECTS_BRANCH = (
            projects_branch if projects_branch else self.THEMES_BRANCH
        )
        self.STARTER = starter
        self.OFFLINE = offline
        self.HUGO_ARGS = hugo_args
        self.set_instance_vars(
            {
                "version": version,
                "themes_branch": self.THEMES_BRANCH,
                "projects_branch": self.PROJECTS_BRANCH,
                "prefix": self.PREFIX,
                "starter": self.STARTER,
                "offline": self.OFFLINE,
            }
        )

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """
        template_vars = get_template_vars()
        starter = Website.objects.get(name=settings.ROOT_WEBSITE_NAME).starter
        starter_path_url = urlparse(starter.path)
        hugo_projects_url = urljoin(
            f"{starter_path_url.scheme}://{starter_path_url.netloc}",
            f"{'/'.join(starter_path_url.path.strip('/').split('/')[:2])}.git",  # /<org>/<repo>.git
        )
        if settings.CONCOURSE_IS_PRIVATE_REPO:
            markdown_uri = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}"
            private_key_var = "((git-private-key))"
        else:
            markdown_uri = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}"
            private_key_var = ""

        if self.VERSION == VERSION_DRAFT:
            template_vars.update(
                {
                    "branch": settings.GIT_BRANCH_PREVIEW,
                    "static_api_url": settings.STATIC_API_BASE_URL
                    or settings.OCW_STUDIO_DRAFT_URL
                    if is_dev()
                    else settings.OCW_STUDIO_DRAFT_URL,
                    "web_bucket": template_vars["preview_bucket_name"],
                    "offline_bucket": template_vars["offline_preview_bucket_name"],
                    "build_drafts": "--buildDrafts",
                    "resource_base_url": settings.RESOURCE_BASE_URL_DRAFT,
                    "noindex": "true",
                }
            )
        elif self.VERSION == VERSION_LIVE:
            template_vars.update(
                {
                    "branch": settings.GIT_BRANCH_RELEASE,
                    "static_api_url": settings.STATIC_API_BASE_URL
                    or settings.OCW_STUDIO_LIVE_URL
                    if is_dev()
                    else settings.OCW_STUDIO_LIVE_URL,
                    "web_bucket": template_vars["publish_bucket_name"],
                    "offline_bucket": template_vars["offline_publish_bucket_name"],
                    "build_drafts": "",
                    "resource_base_url": settings.RESOURCE_BASE_URL_LIVE,
                    "noindex": "true"
                    if settings.ENV_NAME not in PRODUCTION_NAMES
                    else "false",
                }
            )
        base_hugo_args = {
            "--themesDir": "../ocw-hugo-themes/",
            "--quiet": "",
        }
        base_online_args = base_hugo_args.copy()
        base_online_args.update(
            {
                "--baseURL": "$PREFIX/$BASE_URL",
                "--config": "../ocw-hugo-projects/$STARTER_SLUG/config.yaml",
            }
        )
        base_offline_args = base_hugo_args.copy()
        base_offline_args.update(
            {
                "--baseURL": "/",
                "--config": "../ocw-hugo-projects/$STARTER_SLUG/config-offline.yaml",
            }
        )
        hugo_args_online = get_hugo_arg_string(
            TARGET_ONLINE,
            self.VERSION,
            base_online_args,
            self.HUGO_ARGS,
        )
        hugo_args_offline = get_hugo_arg_string(
            TARGET_OFFLINE,
            self.VERSION,
            base_offline_args,
            self.HUGO_ARGS,
        )

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/mass-build-sites.yml", offline=self.OFFLINE
            )
            .replace("((hugo-args-online))", hugo_args_online)
            .replace("((hugo-args-offline))", hugo_args_offline)
            .replace("((markdown-uri))", markdown_uri)
            .replace("((git-private-key-var))", private_key_var)
            .replace("((gtm-account-id))", settings.OCW_GTM_ACCOUNT_ID)
            .replace(
                "((artifacts-bucket))", template_vars["artifacts_bucket_name"] or ""
            )
            .replace("((web-bucket))", template_vars["web_bucket"] or "")
            .replace("((offline-bucket))", template_vars["offline_bucket"] or "")
            .replace("((ocw-hugo-themes-branch))", self.THEMES_BRANCH)
            .replace("((ocw-hugo-themes-uri))", OCW_HUGO_THEMES_GIT)
            .replace(
                "((ocw-hugo-projects-branch))",
                (settings.OCW_HUGO_PROJECTS_BRANCH or self.PROJECTS_BRANCH)
                if is_dev()
                else self.PROJECTS_BRANCH,
            )
            .replace("((ocw-hugo-projects-uri))", hugo_projects_url)
            .replace("((ocw-import-starter-slug))", settings.OCW_COURSE_STARTER_SLUG)
            .replace("((ocw-course-starter-slug))", settings.OCW_COURSE_STARTER_SLUG)
            .replace("((ocw-studio-url))", template_vars["ocw_studio_url"] or "")
            .replace("((static-api-base-url))", template_vars["static_api_url"] or "")
            .replace("((ocw-studio-bucket))", settings.AWS_STORAGE_BUCKET_NAME or "")
            .replace("((ocw-site-repo-branch))", template_vars["branch"] or "")
            .replace("((version))", self.VERSION)
            .replace("((api-token))", settings.API_BEARER_TOKEN or "")
            .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
            .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
            .replace("((build-drafts))", template_vars["build_drafts"] or "")
            .replace("((sitemap-domain))", settings.SITEMAP_DOMAIN)
            .replace("((endpoint-url))", DEV_ENDPOINT_URL)
            .replace(
                "((cli-endpoint-url))",
                f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            )
            .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            .replace("((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or "")
            .replace("((resource-base-url))", template_vars["resource_base_url"])
            .replace("((prefix))", self.PREFIX)
            .replace("((search-api-url))", settings.SEARCH_API_URL)
            .replace("((starter))", f"&starter={self.STARTER}" if self.STARTER else "")
            .replace(
                "((trigger))",
                str(
                    self.THEMES_BRANCH == settings.GITHUB_WEBHOOK_BRANCH
                    and self.PROJECTS_BRANCH == settings.GITHUB_WEBHOOK_BRANCH
                ),
            )
            .replace(
                "((ocw-hugo-themes-sentry-dsn))",
                settings.OCW_HUGO_THEMES_SENTRY_DSN or "",
            )
            .replace("((noindex))", template_vars["noindex"])
        )
        self.upsert_config(config_str, self.PIPELINE_NAME)


class UnpublishedSiteRemovalPipeline(
    BaseUnpublishedSiteRemovalPipeline, GeneralPipeline
):
    """Specialized concourse pipeline for removing unpublished sites"""

    PIPELINE_NAME = BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME

    def __init__(self, api: Optional[PipelineApi] = None):
        """Initialize the pipeline instance"""
        self.MANDATORY_SETTINGS = MANDATORY_CONCOURSE_SETTINGS + [
            "AWS_PUBLISH_BUCKET_NAME"
        ]
        super().__init__(api=api)
        self.pipeline_name = "remove_unpublished_sites"
        self.VERSION = VERSION_LIVE

    def upsert_pipeline(self):  # pylint:disable=too-many-locals
        """
        Create or update the concourse pipeline
        """
        template_vars = get_template_vars()
        web_bucket = template_vars["publish_bucket_name"]
        offline_bucket = template_vars["offline_publish_bucket_name"]

        config_str = (
            self.get_pipeline_definition(
                "definitions/concourse/remove-unpublished-sites.yml"
            )
            .replace("((web-bucket))", web_bucket)
            .replace("((offline-bucket))", offline_bucket)
            .replace("((ocw-studio-url))", template_vars["ocw_studio_url"] or "")
            .replace("((version))", VERSION_LIVE)
            .replace("((api-token))", settings.API_BEARER_TOKEN or "")
            .replace("((open-discussions-url))", settings.OPEN_DISCUSSIONS_URL)
            .replace("((open-webhook-key))", settings.OCW_NEXT_SEARCH_WEBHOOK_KEY)
            .replace(
                "((cli-endpoint-url))",
                f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else "",
            )
            .replace("((minio-root-user))", settings.AWS_ACCESS_KEY_ID or "")
            .replace("((minio-root-password))", settings.AWS_SECRET_ACCESS_KEY or "")
        )
        log.debug(config_str)
        self.upsert_config(config_str, self.PIPELINE_NAME)
