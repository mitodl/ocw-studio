from ol_concourse.lib.constants import REGISTRY_IMAGE
from ol_concourse.lib.models.pipeline import ResourceType

from content_sync.pipelines.definitions.concourse.common.identifiers import (
    HTTP_RESOURCE_TYPE_IDENTIFIER,
    KEYVAL_RESOURCE_TYPE_IDENTIFIER,
    S3_IAM_RESOURCE_TYPE_IDENTIFIER,
)


class HttpResourceType(ResourceType):
    """
    A Resource for making HTTP requests
    """
    def __init__(self, **kwargs):
        super().__init__(
            name=HTTP_RESOURCE_TYPE_IDENTIFIER,
            type=REGISTRY_IMAGE,
            source={"repository": "jgriff/http-resource", "tag": "latest"},
            **kwargs
        )


class KeyvalResourceType(ResourceType):
    """
    A resource for storing and recalling simple key / value pairs
    """
    def __init__(self, **kwargs):
        super().__init__(
            name=KEYVAL_RESOURCE_TYPE_IDENTIFIER,
            type=REGISTRY_IMAGE,
            source={
                "repository": "ghcr.io/cludden/concourse-keyval-resource",
                "tag": "latest",
            },
            **kwargs
        )


class S3IamResourceType(ResourceType):
    """
    A resource for interacting with S3-compatible storage services that supports instance profiles
    """
    def __init__(self, **kwargs):
        super().__init__(
            name=S3_IAM_RESOURCE_TYPE_IDENTIFIER,
            type=REGISTRY_IMAGE,
            source={"repository": "governmentpaas/s3-resource", "tag": "latest"},
            **kwargs
        )
