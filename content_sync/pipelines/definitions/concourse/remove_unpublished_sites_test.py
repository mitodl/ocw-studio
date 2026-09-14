import json

from content_sync.constants import VERSION_LIVE
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    get_fastly_identifier,
)
from content_sync.pipelines.definitions.concourse.common.resources import (
    FASTLY_PURPOSE_LEARN,
)
from content_sync.pipelines.definitions.concourse.remove_unpublished_sites import (
    UnpublishedSiteRemovalPipelineDefinition,
)
from content_sync.utils import get_cli_endpoint_url, get_common_pipeline_vars
from main.utils import is_dev


def test_generate_unpublished_site_removal_pipeline_definition(  # noqa: PLR0915
    mock_environments, settings
):
    """
    The unpublished site removal pipeline definition should contain the expected properties
    """
    open_webhook_key = "abc123"
    open_catalog_urls = [
        "https://example.com/api/v0/ocw_next_webhook/",
        "http://other_example.com/api/v1/ocw_next_webhook/",
    ]
    common_pipeline_vars = get_common_pipeline_vars()
    cli_endpoint_url = get_cli_endpoint_url()
    web_bucket = common_pipeline_vars["publish_bucket_name"]
    offline_bucket = common_pipeline_vars["offline_publish_bucket_name"]
    settings.OPEN_CATALOG_URLS = open_catalog_urls
    settings.OPEN_CATALOG_WEBHOOK_KEY = open_webhook_key

    pipeline_definition = UnpublishedSiteRemovalPipelineDefinition()
    rendered_definition = json.loads(pipeline_definition.json(indent=2))

    jobs = [
        job
        for job in rendered_definition["jobs"]
        if job["name"] == pipeline_definition._remove_unpublished_sites_job_identifier  # noqa: SLF001
    ]
    assert len(jobs) == 1
    remove_unpublished_sites_job = jobs[0]
    get_unpublished_sites_tasks = [
        task
        for task in remove_unpublished_sites_job["plan"]
        if task.get("task")
        == pipeline_definition._get_unpublished_sites_task_identifier  # noqa: SLF001
    ]
    assert len(get_unpublished_sites_tasks) == 1
    get_unpublished_sites_task = get_unpublished_sites_tasks[0]
    get_unpublished_sites_command = " ".join(
        get_unpublished_sites_task["config"]["run"]["args"]
    )
    assert (
        pipeline_definition._unpublished_sites_output_identifier  # noqa: SLF001
        in get_unpublished_sites_command
    )
    search_index_removal_tasks = [
        task
        for task in remove_unpublished_sites_job["plan"]
        if task.get("load_var") == pipeline_definition._unpublished_sites_var_identifier  # noqa: SLF001
    ]
    assert len(search_index_removal_tasks) == 1
    load_unpublished_sites_task = search_index_removal_tasks[0]
    assert (
        load_unpublished_sites_task["file"]
        == f"{pipeline_definition._unpublished_sites_output_identifier}/sites.json"  # noqa: SLF001
    )
    assert load_unpublished_sites_task["format"] == "json"
    assert load_unpublished_sites_task["reveal"] is True
    across_step = remove_unpublished_sites_job["plan"][-1]
    across_var = across_step["across"][0]
    assert across_var["var"] == "site"
    assert (
        across_var["values"]
        == f"((.:{pipeline_definition._unpublished_sites_var_identifier}.sites))"  # noqa: SLF001
    )
    assert across_var["max_in_flight"] == 5
    across_tasks = across_step["do"]
    if not is_dev():
        search_index_removal_tasks = [
            task
            for task in across_tasks
            if pipeline_definition._search_index_removal_task_prefix  # noqa: SLF001
            in (task.get("task") or "")
        ]
        assert len(search_index_removal_tasks) == len(open_catalog_urls)
        for idx, task in enumerate(search_index_removal_tasks):
            search_index_removal_command = " ".join(task["config"]["run"]["args"])
            assert (
                f'"webhook_key": "{open_webhook_key}"' in search_index_removal_command
            )
            assert f'"version": "{VERSION_LIVE}"' in search_index_removal_command
            assert f"{open_catalog_urls[idx]}" in search_index_removal_command
        base_identifier = pipeline_definition._clear_cdn_cache_task_identifier  # noqa: SLF001
        clear_cdn_cache_tasks = [
            task
            for task in across_tasks
            if (task.get("put") or "").startswith(base_identifier)
        ]
        # The live distribution, plus MIT Learn which also serves this content
        assert [task["put"] for task in clear_cdn_cache_tasks] == [
            base_identifier,
            f"{base_identifier}-{FASTLY_PURPOSE_LEARN}",
        ]
        assert [task["resource"] for task in clear_cdn_cache_tasks] == [
            get_fastly_identifier(VERSION_LIVE),
            get_fastly_identifier(FASTLY_PURPOSE_LEARN),
        ]
        for clear_cdn_cache_task in clear_cdn_cache_tasks:
            # The surrogate key is an across var resolved by Concourse at runtime, so
            # it must survive into the put params verbatim
            assert clear_cdn_cache_task["params"]["surrogate_key"] == "((.:site.name))"
            assert clear_cdn_cache_task["params"]["mode"] == "surrogate_key"
            assert clear_cdn_cache_task["no_get"] is True
            assert clear_cdn_cache_task["on_failure"] is not None
        # Success is reported once, after every distribution has been purged
        assert clear_cdn_cache_tasks[0].get("on_success") is None
        assert clear_cdn_cache_tasks[-1].get("on_success") is not None
    empty_s3_buckets_tasks = [
        task
        for task in across_tasks
        if task.get("task") == pipeline_definition._empty_s3_bucket_task_identifier  # noqa: SLF001
    ]
    assert len(empty_s3_buckets_tasks) == 1
    empty_s3_buckets_task = empty_s3_buckets_tasks[0]
    empty_s3_buckets_command = " ".join(empty_s3_buckets_task["config"]["run"]["args"])
    assert (
        f"aws s3{cli_endpoint_url} rm s3://{web_bucket}/((.:site.site_url))/ --recursive"
        in empty_s3_buckets_command
    )
    assert (
        f"aws s3{cli_endpoint_url} rm s3://{offline_bucket}/((.:site.site_url))/ --recursive"
        in empty_s3_buckets_command
    )
    if is_dev():
        assert (
            empty_s3_buckets_task["params"]["AWS_ACCESS_KEY_ID"]
            == settings.AWS_ACCESS_KEY_ID
        )
        assert (
            empty_s3_buckets_task["params"]["AWS_SECRET_ACCESS_KEY"]
            == settings.AWS_SECRET_ACCESS_KEY
        )
