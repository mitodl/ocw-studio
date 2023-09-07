from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import AnonymousResource, RegistryImage

"""
Docker image for building OCW sites

https://github.com/mitodl/ol-infrastructure/tree/main/dockerfiles/ocw/node-hugo
"""
OCW_COURSE_PUBLISHER_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE,
    source=RegistryImage(repository="mitodl/ocw-course-publisher", tag="0.6"),
)

AWS_CLI_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="amazon/aws-cli", tag="latest")
)

CURL_REGISTRY_IMAGE = AnonymousResource(
    type=REGISTRY_IMAGE, source=RegistryImage(repository="curlimages/curl")
)
