from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import AnonymousResource, RegistryImage

"""
Docker image for building OCW sites

https://github.com/mitodl/ol-infrastructure/tree/main/dockerfiles/ocw/node-hugo
"""
OCW_COURSE_PUBLISHER_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE,
    source=RegistryImage(repository="mitodl/ocw-course-publisher", tag="0.8"),
)

AWS_CLI_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE,
    source=RegistryImage(repository="amazon/aws-cli", tag="2.27.50"),
)

BASH_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="bash", tag="latest")
)

CURL_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="curlimages/curl")
)

PLAYWRIGHT_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE,
    source=RegistryImage(
        repository="mcr.microsoft.com/playwright", tag="v1.40.0-jammy"
    ),
)
