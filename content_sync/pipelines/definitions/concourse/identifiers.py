from ol_concourse.lib.models.pipeline import Identifier


HTTP_RESOURCE_TYPE_IDENTIFIER = Identifier("http-resource")
KEYVAL_RESOURCE_TYPE_IDENTIFIER = Identifier("keyval")
S3_IAM_RESOURCE_TYPE_IDENTIFIER = Identifier("s3-resource-iam")
OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER = Identifier("ocw-studio-webhook")
SLACK_ALERT_RESOURCE_IDENTIFIER = Identifier("slack-alert")
OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER = Identifier("open-discussions-webhook")

webpack_json_identifier = Identifier("webpack-json")
ocw_hugo_themes_identifier = Identifier("ocw-hugo-themes")
ocw_hugo_projects_identifier = Identifier("ocw-hugo-projects")
site_content_identifier = Identifier("site-content")
static_resources_identifier = Identifier("static-resources")
offline_build_gate_identifier = Identifier("offline-build-gate")
online_site_job_identifier = Identifier("online-site-job")
build_online_site_identifier = Identifier("build-online-site")
upload_online_build_identifier = Identifier("upload-online-build")
build_artifacts_identifier = Identifier("build-artifacts")
filter_webpack_artifacts_identifier = Identifier("filter-webpack-artifacts")
offline_site_job_identifier = Identifier("offline-site-job")
build_offline_site_identifier = Identifier("build-offline-site")
upload_offline_build_identifier = Identifier("upload-offline-build")
