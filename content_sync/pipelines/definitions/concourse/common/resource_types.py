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
            source={"repository": "umar8hassan/http-resource", "tag": "latest"},
            **kwargs,
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
            **kwargs,
        )


class S3IamResourceType(ResourceType):
    """
    A resource for interacting with S3-compatible storage services that supports
    instance profiles.

    This used to point at governmentpaas/s3-resource, a fork we adopted in #966
    because the official resource could not authenticate via an EC2 instance
    profile. #1763 tried to move back and had to be reverted in #1780 for that
    same reason. Upstream gained support for the AWS default credential provider
    in May 2025 (concourse/s3-resource@40e8034), so the fork is no longer needed.

    Resources of this type must set `enable_aws_creds_provider: True` in their
    source to opt into that chain -- without it the official resource falls back
    to anonymous credentials. See WebpackManifestResource.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name=S3_IAM_RESOURCE_TYPE_IDENTIFIER,
            type=REGISTRY_IMAGE,
            source={"repository": "concourse/s3-resource", "tag": "latest"},
            **kwargs,
        )
