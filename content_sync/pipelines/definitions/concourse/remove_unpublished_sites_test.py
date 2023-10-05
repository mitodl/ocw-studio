import json

from content_sync.constants import VERSION_LIVE
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
    open_discussions_url = "https://example.com"
    common_pipeline_vars = get_common_pipeline_vars()
    cli_endpoint_url = get_cli_endpoint_url()
    web_bucket = common_pipeline_vars["publish_bucket_name"]
    offline_bucket = common_pipeline_vars["offline_publish_bucket_name"]
    settings.OPEN_DISCUSSIONS_URL = open_discussions_url
    settings.OCW_NEXT_SEARCH_WEBHOOK_KEY = open_webhook_key

    pipeline_definition = UnpublishedSiteRemovalPipelineDefinition()
    rendered_definition = json.loads(pipeline_definition.json(indent=2))

    jobs = [
        job
        for job in rendered_definition["jobs"]
        if job["name"]
        == pipeline_definition._remove_unpublished_sites_job_identifier  # noqa: SLF001
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
        pipeline_definition._unpublishable_sites_output_identifier  # noqa: SLF001
        in get_unpublished_sites_command
    )
    search_index_removal_tasks = [
        task
        for task in remove_unpublished_sites_job["plan"]
        if task.get("load_var")
        == pipeline_definition._unpublishable_sites_var_identifier  # noqa: SLF001
    ]
    assert len(search_index_removal_tasks) == 1
    load_unpublishable_sites_task = search_index_removal_tasks[0]
    assert (
        load_unpublishable_sites_task["file"]
        == f"{pipeline_definition._unpublishable_sites_output_identifier}/sites.json"  # noqa: SLF001
    )
    assert load_unpublishable_sites_task["format"] == "json"
    assert load_unpublishable_sites_task["reveal"] is True
    across_step = remove_unpublished_sites_job["plan"][-1]
    across_var = across_step["across"][0]
    assert across_var["var"] == "site"
    assert (
        across_var["values"]
        == f"((.:{pipeline_definition._unpublishable_sites_var_identifier}.sites))"  # noqa: SLF001
    )
    assert across_var["max_in_flight"] == 5
    across_tasks = across_step["do"]
    if not is_dev():
        search_index_removal_tasks = [
            task
            for task in across_tasks
            if task.get("task")
            == pipeline_definition._search_index_removal_task_identifier  # noqa: SLF001
        ]
        assert len(search_index_removal_tasks) == 1
        search_index_removal_task = search_index_removal_tasks[0]
        search_index_removal_command = " ".join(
            search_index_removal_task["config"]["run"]["args"]
        )
        assert f'"webhook_key": "{open_webhook_key}"' in search_index_removal_command
        assert f'"version": "{VERSION_LIVE}"' in search_index_removal_command
        assert (
            f"{open_discussions_url}/api/v0/ocw_next_webhook/"
            in search_index_removal_command
        )
        clear_cdn_cache_tasks = [
            task
            for task in across_tasks
            if task.get("task")
            == pipeline_definition._clear_cdn_cache_task_identifier  # noqa: SLF001
        ]
        assert len(clear_cdn_cache_tasks) == 1
        clear_cdn_cache_task = clear_cdn_cache_tasks[0]
        assert clear_cdn_cache_task["on_success"] is not None
        assert clear_cdn_cache_task["on_failure"] is not None
    empty_s3_buckets_tasks = [
        task
        for task in across_tasks
        if task.get("task")
        == pipeline_definition._empty_s3_bucket_task_identifier  # noqa: SLF001
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
