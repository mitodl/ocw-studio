import json
from urllib.parse import quote

import pytest

from content_sync.constants import DEV_ENDPOINT_URL
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
)
from content_sync.pipelines.definitions.concourse.theme_assets_pipeline import (
    ThemeAssetsPipelineDefinition,
)


@pytest.mark.parametrize("is_dev", [True, False])
def test_generate_theme_assets_pipeline_definition(mocker, is_dev):
    """
    The theme assets pipeline definition should contain the expected properties
    """
    mock_is_dev = mocker.patch(
        "content_sync.pipelines.definitions.concourse.theme_assets_pipeline.is_dev"
    )
    mock_is_dev.return_value = is_dev
    artifacts_bucket = "ol-eng-artifacts"
    preview_bucket = "ocw-content-preview"
    publish_bucket = "ocw-content-publish"
    ocw_hugo_themes_branch = "main"
    instance_vars = f"?vars={quote(json.dumps({'branch': ocw_hugo_themes_branch}))}"
    pipeline_definition = ThemeAssetsPipelineDefinition(
        artifacts_bucket=artifacts_bucket,
        preview_bucket=preview_bucket,
        publish_bucket=publish_bucket,
        ocw_hugo_themes_branch=ocw_hugo_themes_branch,
        instance_vars=instance_vars,
    )
    rendered_definition = json.loads(pipeline_definition.json(indent=2))
    git_resources = [
        resource
        for resource in rendered_definition["resources"]
        if resource["name"] == OCW_HUGO_THEMES_GIT_IDENTIFIER
    ]
    assert len(git_resources) == 1
    git_resource = git_resources[0]
    assert git_resource["source"]["branch"] == ocw_hugo_themes_branch

    jobs = [
        job
        for job in rendered_definition["jobs"]
        if job["name"] == pipeline_definition._build_theme_assets_job_identifier
    ]
    assert len(jobs) == 1
    build_theme_assets_job = jobs[0]
    build_ocw_hugo_themes_tasks = [
        task
        for task in build_theme_assets_job["plan"]
        if task.get("task") == pipeline_definition._build_ocw_hugo_themes_identifier
    ]
    assert len(build_ocw_hugo_themes_tasks) == 1
    build_ocw_hugo_themes_task = build_ocw_hugo_themes_tasks[0]
    build_ocw_hugo_themes_command = " ".join(
        build_ocw_hugo_themes_task["config"]["run"]["args"]
    )
    assert OCW_HUGO_THEMES_GIT_IDENTIFIER in build_ocw_hugo_themes_command
    upload_theme_assets_tasks = [
        task
        for task in build_theme_assets_job["plan"]
        if task.get("task") == pipeline_definition._upload_theme_assets_task_identifier
    ]
    assert len(upload_theme_assets_tasks) == 1
    upload_theme_assets_task = upload_theme_assets_tasks[0]
    upload_theme_assets_command = " ".join(
        upload_theme_assets_task["config"]["run"]["args"]
    )
    assert artifacts_bucket in upload_theme_assets_command
    assert preview_bucket in upload_theme_assets_command
    assert publish_bucket in upload_theme_assets_command
    if is_dev:
        assert f" --endpoint-url {DEV_ENDPOINT_URL}" in upload_theme_assets_command
        assert "AWS_ACCESS_KEY_ID" in upload_theme_assets_task["config"]["params"]
        assert "AWS_SECRET_ACCESS_KEY" in upload_theme_assets_task["config"]["params"]
