from urllib.parse import urlparse

from django.utils.text import slugify
from ol_concourse.lib.models.pipeline import Identifier

# Commonly used identifiers
HTTP_RESOURCE_TYPE_IDENTIFIER = Identifier("http-resource").root
KEYVAL_RESOURCE_TYPE_IDENTIFIER = Identifier("keyval").root
S3_IAM_RESOURCE_TYPE_IDENTIFIER = Identifier("s3-resource-iam").root
OCW_STUDIO_WEBHOOK_RESOURCE_TYPE_IDENTIFIER = Identifier("ocw-studio-webhook").root
OCW_STUDIO_WEBHOOK_CURL_STEP_IDENTIFIER = Identifier("ocw-studio-webhook-curl").root
SLACK_ALERT_RESOURCE_IDENTIFIER = Identifier("slack-alert").root
WEBPACK_MANIFEST_S3_IDENTIFIER = Identifier("webpack-manifest-s3").root
WEBPACK_MANIFEST_S3_TRIGGER_IDENTIFIER = Identifier(
    f"{WEBPACK_MANIFEST_S3_IDENTIFIER}-trigger"
).root
WEBPACK_ARTIFACTS_IDENTIFIER = Identifier("webpack-artifacts").root
OCW_HUGO_THEMES_GIT_IDENTIFIER = Identifier("ocw-hugo-themes-git").root
OCW_HUGO_PROJECTS_GIT_IDENTIFIER = Identifier("ocw-hugo-projects-git").root
OCW_HUGO_PROJECTS_GIT_TRIGGER_IDENTIFIER = Identifier(
    f"{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}-trigger"
).root
SITE_CONTENT_GIT_IDENTIFIER = Identifier("site-content-git").root
STATIC_RESOURCES_S3_IDENTIFIER = Identifier("static-resources-s3").root
MASS_BULID_SITES_PIPELINE_IDENTIFIER = Identifier("mass-build-sites").root
MASS_BUILD_SITES_JOB_IDENTIFIER = Identifier("mass-build-sites-job").root
MASS_BUILD_SITES_BATCH_GATE_IDENTIFIER = Identifier("batch-gate").root


def get_ocw_catalog_identifier(url: str):
    """
    Get the identifier for a given OCW Catalog URL

    Args:
        url(str): The URL of the OCW Catalog

    Returns:
        Identifier
    """
    return Identifier(f"open-catalog-webhook-{slugify(urlparse(url).netloc)}").root
