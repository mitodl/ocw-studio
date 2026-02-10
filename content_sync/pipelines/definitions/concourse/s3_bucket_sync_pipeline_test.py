import json

from django.conf import settings

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.s3_bucket_sync_pipeline import (
    S3BucketSyncPipelineDefinition,
    s3_sync_job_identifier,
    s3_sync_task_identifier,
    s3_sync_timer_identifier,
)
from main.utils import is_dev


def test_generate_s3_bucket_sync_pipeline_definition(mocker):
    """
    The S3 bucket sync pipeline definition should contain the expected properties
    """
    import_bucket = "test-import-bucket"
    storage_bucket = "test-storage-bucket"
    sync_interval = "12h"

    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.s3_bucket_sync_pipeline.is_dev"
    )
    mock_is_dev.return_value = False

    settings.AWS_MAX_CONCURRENT_CONNECTIONS = 20

    pipeline_definition = S3BucketSyncPipelineDefinition(
        import_bucket=import_bucket,
        storage_bucket=storage_bucket,
        sync_interval=sync_interval,
    )
    rendered_definition = json.loads(pipeline_definition.json(indent=2, by_alias=True))

    # Assert that the time resource exists with the correct interval
    timer_resources = [
        resource
        for resource in rendered_definition["resources"]
        if resource["name"] == s3_sync_timer_identifier
    ]
    assert len(timer_resources) == 1
    timer_resource = timer_resources[0]
    assert timer_resource["type"] == "time"
    assert timer_resource["source"]["interval"] == sync_interval

    # Assert that the job exists
    jobs = [
        job for job in rendered_definition["jobs"] if job["name"] == s3_sync_job_identifier
    ]
    assert len(jobs) == 1
    job = jobs[0]
    assert job["serial"] is True

    # Assert that the sync task exists with the correct command
    sync_tasks = [
        task for task in job["plan"] if task.get("task") == s3_sync_task_identifier
    ]
    assert len(sync_tasks) == 1
    sync_task = sync_tasks[0]
    sync_command = " ".join(sync_task["config"]["run"]["args"])
    assert f"aws s3 sync s3://{import_bucket}/ s3://{storage_bucket}/" in sync_command
    assert "aws configure set default.s3.max_concurrent_requests $AWS_MAX_CONCURRENT_CONNECTIONS" in sync_command
    # When not in dev mode, should not have endpoint URL
    assert "--endpoint-url" not in sync_command
    # Assert that AWS_MAX_CONCURRENT_CONNECTIONS is in params
    assert "AWS_MAX_CONCURRENT_CONNECTIONS" in sync_task["config"]["params"]
    assert sync_task["config"]["params"]["AWS_MAX_CONCURRENT_CONNECTIONS"] == "20"


def test_generate_s3_bucket_sync_pipeline_definition_dev_mode(mocker):
    """
    The S3 bucket sync pipeline definition should include dev endpoint URL when in dev mode
    """
    import_bucket = "test-import-bucket"
    storage_bucket = "test-storage-bucket"
    sync_interval = "6h"

    settings.AWS_ACCESS_KEY_ID = "test_key"
    settings.AWS_SECRET_ACCESS_KEY = "test_secret"  # noqa: S105
    settings.AWS_MAX_CONCURRENT_CONNECTIONS = 15

    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.s3_bucket_sync_pipeline.is_dev"
    )
    mock_is_dev.return_value = True

    pipeline_definition = S3BucketSyncPipelineDefinition(
        import_bucket=import_bucket,
        storage_bucket=storage_bucket,
        sync_interval=sync_interval,
    )
    rendered_definition = json.loads(pipeline_definition.json(indent=2, by_alias=True))

    # Assert that the job exists
    jobs = [
        job for job in rendered_definition["jobs"] if job["name"] == s3_sync_job_identifier
    ]
    assert len(jobs) == 1
    job = jobs[0]

    # Assert that the sync task includes dev endpoint URL
    sync_tasks = [
        task for task in job["plan"] if task.get("task") == s3_sync_task_identifier
    ]
    assert len(sync_tasks) == 1
    sync_task = sync_tasks[0]
    sync_command = " ".join(sync_task["config"]["run"]["args"])
    assert f"--endpoint-url {DEV_ENDPOINT_URL}" in sync_command
    assert f"aws s3 --endpoint-url {DEV_ENDPOINT_URL} sync s3://{import_bucket}/ s3://{storage_bucket}/" in sync_command
    assert "aws configure set default.s3.max_concurrent_requests $AWS_MAX_CONCURRENT_CONNECTIONS" in sync_command

    # Assert that AWS credentials and max concurrent connections are in params when in dev mode
    assert "AWS_ACCESS_KEY_ID" in sync_task["config"]["params"]
    assert "AWS_SECRET_ACCESS_KEY" in sync_task["config"]["params"]
    assert "AWS_MAX_CONCURRENT_CONNECTIONS" in sync_task["config"]["params"]
    assert sync_task["config"]["params"]["AWS_ACCESS_KEY_ID"] == settings.AWS_ACCESS_KEY_ID
    assert (
        sync_task["config"]["params"]["AWS_SECRET_ACCESS_KEY"]
        == settings.AWS_SECRET_ACCESS_KEY
    )
    assert sync_task["config"]["params"]["AWS_MAX_CONCURRENT_CONNECTIONS"] == "15"
