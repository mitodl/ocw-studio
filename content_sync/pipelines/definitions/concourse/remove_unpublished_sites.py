import json

from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    AcrossVar,
    Command,
    DoStep,
    Identifier,
    Job,
    LoadVarStep,
    Output,
    Pipeline,
    TaskConfig,
    TaskStep,
)

from content_sync.constants import DEV_ENDPOINT_URL, VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    get_ocw_catalog_identifier,
)
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
    BASH_REGISTRY_IMAGE,
    CURL_REGISTRY_IMAGE,
)
from content_sync.pipelines.definitions.concourse.common.resource_types import (
    HttpResourceType,
    S3IamResourceType,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    OpenCatalogResource,
    SlackAlertResource,
)
from content_sync.pipelines.definitions.concourse.common.steps import (
    ClearCdnCacheStep,
    OcwStudioWebhookCurlStep,
)
from content_sync.utils import (
    get_cli_endpoint_url,
    get_common_pipeline_vars,
    get_ocw_studio_api_url,
)
from main.utils import is_dev

CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""


class UnpublishedSiteRemovalPipelineDefinition(Pipeline):
    """
    A Pipeline that does the following:

     - Fetch a list of unpublished sites from the ocw-studio API
     - For each site:
       - Remove from Open search index
       - Remove the site from S3
       - Clear CDN cache
    """

    _remove_unpublished_sites_job_identifier = Identifier(
        "remove-unpublished-sites-job"
    ).root
    _get_unpublished_sites_task_identifier = Identifier(
        "get-unpublished-sites-task"
    ).root
    _unpublished_sites_output_identifier = Identifier("unpublished-sites-output").root
    _unpublished_sites_var_identifier = Identifier("unpublished-sites-var").root
    _search_index_removal_task_prefix = "search-index-removal-task"
    _empty_s3_bucket_task_identifier = Identifier("empty-s3-bucket-task").root
    _clear_cdn_cache_task_identifier = Identifier("clear-cdn-cache-task").root
    _ocw_studio_webhook_task_identifier = Identifier("ocw-studio-webhook-task").root

    _open_catalog_resources = [
        OpenCatalogResource(catalog_url) for catalog_url in settings.OPEN_CATALOG_URLS
    ]
    _slack_resource = SlackAlertResource()

    def __init__(self, **kwargs):
        base = super()
        base.__init__(**kwargs)
        common_pipeline_vars = get_common_pipeline_vars()
        web_bucket = common_pipeline_vars["publish_bucket_name"]
        offline_bucket = common_pipeline_vars["offline_publish_bucket_name"]
        ocw_studio_url = get_ocw_studio_api_url().rstrip("/")
        cli_endpoint_url = get_cli_endpoint_url()
        api_token = settings.API_BEARER_TOKEN
        open_catalog_urls = [
            catalog_url.rstrip("/") for catalog_url in settings.OPEN_CATALOG_URLS
        ]
        open_webhook_key = settings.OCW_NEXT_SEARCH_WEBHOOK_KEY
        minio_root_user = settings.AWS_ACCESS_KEY_ID
        minio_root_password = settings.AWS_SECRET_ACCESS_KEY

        resource_types = [
            HttpResourceType(),
            S3IamResourceType(),
        ]
        unpublish_failed_webhook_across_step = OcwStudioWebhookCurlStep(
            site_name="((.:site.name))",
            data={"version": VERSION_LIVE, "status": "errored", "unpublished": True},
        )
        unpublish_succeeded_webhook_across_step = OcwStudioWebhookCurlStep(
            site_name="((.:site.name))",
            data={
                "version": VERSION_LIVE,
                "status": "succeeded",
                "unpublished": True,
            },
        )
        search_index_removal_across_tasks = [
            TaskStep(
                task=get_ocw_catalog_identifier(
                    catalog_url, prefix=self._search_index_removal_task_prefix
                ),
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
                            "--data",
                            json.dumps(
                                {
                                    "webhook_key": open_webhook_key,
                                    "site_uid": "((.:site.site_uid))",
                                    "version": VERSION_LIVE,
                                    "unpublished": True,
                                }
                            ),
                            f"{catalog_url}/api/v0/ocw_next_webhook/",
                        ],
                    ),
                ),
                on_failure=unpublish_failed_webhook_across_step,
            )
            for catalog_url in open_catalog_urls
        ]
        empty_s3_bucket_across_task = TaskStep(
            task=self._empty_s3_bucket_task_identifier,
            timeout="10m",
            attempts=3,
            params={},
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                run=Command(
                    path="sh",
                    args=[
                        "-exc",
                        f"""
                        aws s3{cli_endpoint_url} rm s3://{web_bucket}/((.:site.site_url))/ --recursive
                        aws s3{cli_endpoint_url} rm s3://{offline_bucket}/((.:site.site_url))/ --recursive
                        """,  # noqa: E501
                    ],
                ),
            ),
            on_failure=unpublish_failed_webhook_across_step,
        )
        if is_dev():
            empty_s3_bucket_across_task.params.update(
                {
                    "AWS_ACCESS_KEY_ID": minio_root_user,
                    "AWS_SECRET_ACCESS_KEY": minio_root_password,
                }
            )
        clear_cdn_cache_step = ClearCdnCacheStep(
            name=self._clear_cdn_cache_task_identifier,
            fastly_var=f"fastly_{VERSION_LIVE}",
            site_name="((.:site.name))",
            on_success=unpublish_succeeded_webhook_across_step,
            on_failure=unpublish_failed_webhook_across_step,
        )
        across_tasks = [
            empty_s3_bucket_across_task,
        ]
        if not is_dev():
            across_tasks.extend(search_index_removal_across_tasks)
            across_tasks.append(clear_cdn_cache_step)
        tasks = [
            TaskStep(
                task=self._get_unpublished_sites_task_identifier,
                timeout="2m",
                attempts=3,
                config=TaskConfig(
                    platform="linux",
                    image_resource=BASH_REGISTRY_IMAGE,
                    outputs=[Output(name=self._unpublished_sites_output_identifier)],
                    run=Command(
                        path="sh",
                        args=[
                            "-exc",
                            f'wget -O {self._unpublished_sites_output_identifier}/sites.json --header="Authorization: Bearer {api_token}" "{ocw_studio_url}/api/unpublish/"',  # noqa: E501
                        ],
                    ),
                ),
            ),
            LoadVarStep(
                load_var=self._unpublished_sites_var_identifier,
                file=f"{self._unpublished_sites_output_identifier}/sites.json",
                format="json",
                reveal=True,
            ),
            DoStep(
                do=across_tasks,
                across=[
                    AcrossVar(
                        var="site",
                        values=f"((.:{self._unpublished_sites_var_identifier}.sites))",
                        max_in_flight=5,
                    )
                ],
            ),
        ]
        job = Job(name=self._remove_unpublished_sites_job_identifier, serial=True)

        job.plan = tasks
        base.__init__(resource_types=resource_types, jobs=[job], **kwargs)
