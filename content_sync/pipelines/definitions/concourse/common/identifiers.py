from ol_concourse.lib.models.pipeline import Identifier

# Commonly used identifiers
HTTP_RESOURCE_TYPE_IDENTIFIER = Identifier("http-resource")
KEYVAL_RESOURCE_TYPE_IDENTIFIER = Identifier("keyval")
S3_IAM_RESOURCE_TYPE_IDENTIFIER = Identifier("s3-resource-iam")
OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER = Identifier("ocw-studio-webhook")
SLACK_ALERT_RESOURCE_IDENTIFIER = Identifier("slack-alert")
OPEN_DISCUSSIONS_RESOURCE_IDENTIFIER = Identifier("open-discussions-webhook")
WEBPACK_MANIFEST_S3_IDENTIFIER = Identifier("webpack-manifest-s3")
WEBPACK_ARTIFACTS_IDENTIFIER = Identifier("webpack-artifacts")
OCW_HUGO_THEMES_GIT_IDENTIFIER = Identifier("ocw-hugo-themes-git")
OCW_HUGO_PROJECTS_GIT_IDENTIFIER = Identifier("ocw-hugo-projects-git")
SITE_CONTENT_GIT_IDENTIFIER = Identifier("site-content-git")
STATIC_RESOURCES_S3_IDENTIFIER = Identifier("static-resources-s3")
