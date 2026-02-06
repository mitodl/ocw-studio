from django.conf import settings
from ol_concourse.lib.models.pipeline import (
    Command,
    GetStep,
    Identifier,
    Job,
    Pipeline,
    Resource,
    TaskConfig,
    TaskStep,
)

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.common.image_resources import (
    AWS_CLI_REGISTRY_IMAGE,
)
from main.utils import is_dev

CLI_ENDPOINT_URL = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev() else ""

s3_sync_timer_identifier = Identifier("s3-sync-timer").root
s3_sync_task_identifier = Identifier("s3-sync-task").root
s3_sync_job_identifier = Identifier("s3-bucket-sync-job").root


class S3BucketSyncPipelineDefinition(Pipeline):
    """
    A Pipeline that syncs S3 buckets periodically:

     - Triggers on a configurable time interval
     - Uses AWS CLI to sync from AWS_IMPORT_STORAGE_BUCKET_NAME to AWS_STORAGE_BUCKET_NAME

    Args:
        import_bucket(str): The S3 bucket to sync from (source)
        storage_bucket(str): The S3 bucket to sync to (destination)
        sync_interval(str): The time interval for syncing (e.g., "24h", "12h", "6h")
    """

    def __init__(
        self,
        import_bucket: str,
        storage_bucket: str,
        sync_interval: str = "24h",
        **kwargs,
    ):
        base = super()
        base.__init__(**kwargs)

        # Time-based trigger resource
        timer_resource = Resource(
            name=s3_sync_timer_identifier,
            type="time",
            icon="clock-outline",
            source={"interval": sync_interval},
        )

        resources = [timer_resource]
        resource_types = []

        # Get step for time trigger
        get_timer_step = GetStep(
            get=s3_sync_timer_identifier,
            trigger=True,
        )

        # AWS S3 sync task
        sync_commands = f"""
        aws s3{CLI_ENDPOINT_URL} sync s3://{import_bucket}/ s3://{storage_bucket}/
        """

        s3_sync_task = TaskStep(
            task=s3_sync_task_identifier,
            timeout="2h",
            attempts=3,
            config=TaskConfig(
                platform="linux",
                image_resource=AWS_CLI_REGISTRY_IMAGE,
                params=(
                    {}
                    if not is_dev()
                    else {
                        "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID or "",
                        "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY or "",
                    }
                ),
                run=Command(
                    path="sh",
                    args=["-exc", sync_commands],
                ),
            ),
        )

        tasks = [get_timer_step, s3_sync_task]
        job = Job(name=s3_sync_job_identifier, serial=True, plan=tasks)

        base.__init__(
            resource_types=resource_types, resources=resources, jobs=[job], **kwargs
        )
