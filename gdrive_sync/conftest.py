"""Common functions and variables for gdrive_sync tests"""

from collections.abc import Iterable
from typing import Optional

import boto3

from websites.constants import CONTENT_TYPE_RESOURCE, WebsiteStarterStatus
from websites.models import Website, WebsiteStarter
from websites.site_config_api import ConfigItem, SiteConfig

LIST_VIDEO_RESPONSES = [
    {
        "nextPageToken": "~!!~AI9FV7Tc4k5BiAr1Ckwyu",
        "files": [
            {
                "id": "12JCgxaoHrGvd_Vy5grfCTHr",
                "name": "test_video_1.mp4",
                "mimeType": "video/mp4",
                "parents": ["1lSSPf_kx83O0fcmSA9n4-c3dnB"],
                "webContentLink": "https://drive.google.com/uc?id=12JCgxaoHrGvd_Vy5grfCTHr&export=download",
                "createdTime": "2021-07-28T00:06:40.439Z",
                "modifiedTime": "2021-07-29T16:25:19.375Z",
                "md5Checksum": "633410252",
                "trashed": False,
            },
            {
                "id": "1Co1ZE7nodTjCqXuyFl10B38",
                "name": "test_video_2.mp4",
                "mimeType": "video/mp4",
                "parents": ["TepPI157C9za"],
                "webContentLink": "https://drive.google.com/uc?id=1Co1ZE7nodTjCqXuyFl10B38&export=download",
                "createdTime": "2019-08-27T12:51:41.000Z",
                "modifiedTime": "2021-07-29T16:25:19.187Z",
                "md5Checksum": "3827293107",
                "trashed": False,
            },
        ],
    },
    {
        "files": [
            {
                "id": "Vy5grfCTHr_12JCgxaoHrGvd",
                "name": "test_video_1.mp4",
                "mimeType": "video/mp4",
                "parents": ["1lSSPf_kx83O0fcmSA9n4-c3dnB"],
                "webContentLink": "https://drive.google.com/uc?id=Vy5grfCTHr_12JCgxaoHrGvd&export=download",
                "createdTime": "2021-07-28T00:06:40.439Z",
                "modifiedTime": "2021-07-29T14:25:19.375Z",
                "md5Checksum": "633410252",
                "trashed": False,
            },
            {
                "id": "XuyFl10B381Co1ZE7nodTjCq",
                "name": "test_video_2.mp4",
                "mimeType": "video/mp4",
                "parents": ["TepPI157C9za"],
                "webContentLink": "https://drive.google.com/uc?id=XuyFl10B381Co1ZE7nodTjCq&export=download",
                "createdTime": "2020-08-27T12:51:41.000Z",
                "modifiedTime": "2021-07-30T12:25:19.187Z",
                "md5Checksum": "3827293107",
                "trashed": False,
            },
        ]
    },
]

LIST_FILE_RESPONSES = [
    {
        "files": [
            {
                "id": "Ay5grfCTHr_12JCgxaoHrGve",
                "name": "test_image.jpg",
                "mimeType": "image/jpeg",
                "parents": ["websiteFileFinalFolderId"],
                "webContentLink": "https://drive.google.com/uc?id=Ay5grfCTHr_12JCgxaoHrGve&export=download",
                "createdTime": "2021-07-28T00:06:40.439Z",
                "modifiedTime": "2021-07-29T14:25:19.375Z",
                "md5Checksum": "633410252",
                "trashed": False,
            },
            {
                "id": "BuyFl10B381Co1ZE7nodTjCr",
                "name": "test_video_wrong_folder.mp4",
                "mimeType": "video/mp4",
                "parents": ["websiteFileFinalFolderId"],
                "webContentLink": "https://drive.google.com/uc?id=BuyFl10B381Co1ZE7nodTjCr&export=download",
                "createdTime": "2020-08-27T12:51:41.000Z",
                "modifiedTime": "2021-07-30T12:25:19.187Z",
                "md5Checksum": "3827293107",
                "trashed": False,
            },
        ]
    },
]


def all_starters_items_fields() -> Iterable[tuple[WebsiteStarter, ConfigItem, dict]]:
    """All fields from all starters."""
    all_starters = list(
        WebsiteStarter.objects.filter(status__in=WebsiteStarterStatus.ALLOWED_STATUSES)
    )
    data = []
    for starter in all_starters:
        for item in SiteConfig(starter.config).iter_items():
            for field in item.fields:
                data.append((starter, item, field))  # noqa: PERF401

    return data


def generate_related_content_data(
    starter: WebsiteStarter, field: dict, resource_id: str, website: Website
) -> Optional[dict]:
    """
    A utility method to create data for WebsiteContent for `field` that references
    `resource_id`.

    Returns `None` for any unrelated field.
    """  # noqa: D401
    if starter != website.starter and not field.get("cross_site", False):
        return None

    if field.get("widget") == "markdown" and (
        CONTENT_TYPE_RESOURCE in field.get("link", [])
        or CONTENT_TYPE_RESOURCE in field.get("embed", [])
    ):
        return {
            "markdown": f'{{{{% resource_link "{resource_id}" "filename" %}}}}',
            "metadata": {},
        }
    elif (
        field.get("widget") == "relation"
        and field.get("collection") == CONTENT_TYPE_RESOURCE
    ):
        value = (
            resource_id
            if not field.get("cross_site", False)
            else [resource_id, website.url_path]
        )

        content = [value] if field.get("multiple", False) else value

        return {"markdown": "", "metadata": {field["name"]: {"content": content}}}
    elif field.get("widget") == "menu":
        return {
            "markdown": r"",
            "metadata": {field["name"]: [{"identifier": resource_id}]},
        }
    return None


def setup_s3_test_file_bucket(settings, file_key: str) -> "s3.Bucket":  # noqa: F821
    """
    Setup a mock s3 service with a fake file and a bucket.

    Returns the bucket.
    """  # noqa: D401
    mock_bucket = settings.AWS_STORAGE_BUCKET_NAME

    s3 = boto3.resource("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=mock_bucket)
    bucket = s3.Bucket(mock_bucket)
    file_content = "This is the content of the fake file."
    bucket.put_object(Key=file_key, Body=file_content)

    return bucket
