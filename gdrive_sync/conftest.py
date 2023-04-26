"""Common functions and variables for gdrive_sync tests"""

from websites.constants import (
    CONTENT_TYPE_COURSE_COLLECTION,
    CONTENT_TYPE_METADATA,
    CONTENT_TYPE_NAVMENU,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_PROMOS,
    CONTENT_TYPE_RESOURCE_COLLECTION,
    CONTENT_TYPE_RESOURCE_LIST,
    CONTENT_TYPE_STORIES,
    CONTENT_TYPE_VIDEO_GALLERY,
)


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


__RESOURCE_ID = "7d3df94e-e8dd-40bc-97f2-18e793d5ce26"
__WEBSITE_URL = "courses/test-site"
RESOURCE_REFERENCES_TEST_DATA = {
    "resource_id": __RESOURCE_ID,
    "website_url": __WEBSITE_URL,
    "contents": [
        [],
        [
            {
                "type": CONTENT_TYPE_PAGE,
                "markdown": f'{{{{% resource_link "{__RESOURCE_ID}" "filename" %}}}}',
                "metadata": {},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_RESOURCE_LIST,
                "markdown": r"",
                "metadata": {"resources": {"content": [__RESOURCE_ID]}},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_METADATA,
                "markdown": r"",
                "metadata": {"course_image": {"content": __RESOURCE_ID}},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_METADATA,
                "markdown": r"",
                "metadata": {"course_image_thumbnail": {"content": __RESOURCE_ID}},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_VIDEO_GALLERY,
                "markdown": r"",
                "metadata": {"videos": {"content": [__RESOURCE_ID]}},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_RESOURCE_COLLECTION,
                "markdown": r"",
                "metadata": {
                    "resources": {
                        "content": [
                            [
                                __RESOURCE_ID,
                                __WEBSITE_URL,
                            ]
                        ]
                    }
                },
            }
        ],
        [
            {
                "type": CONTENT_TYPE_COURSE_COLLECTION,
                "markdown": r"",
                "metadata": {
                    "cover-image": {
                        "content": __RESOURCE_ID,
                        "website": "ocw-www",
                    }
                },
            }
        ],
        [
            {
                "type": CONTENT_TYPE_STORIES,
                "markdown": r"",
                "metadata": {
                    "image": {
                        "content": __RESOURCE_ID,
                        "website": "ocw-www",
                    }
                },
            }
        ],
        [
            {
                "type": CONTENT_TYPE_PROMOS,
                "markdown": r"",
                "metadata": {
                    "image": {
                        "content": __RESOURCE_ID,
                        "website": "ocw-www",
                    }
                },
            }
        ],
        [
            {
                "type": CONTENT_TYPE_NAVMENU,
                "markdown": r"",
                "metadata": {"leftnav": [{"identifier": __RESOURCE_ID}]},
            }
        ],
        [
            {
                "type": CONTENT_TYPE_PAGE,
                "markdown": f'{{{{% resource_link "{__RESOURCE_ID}" "filename" %}}}}',
                "metadata": {},
            },
            {
                "type": CONTENT_TYPE_METADATA,
                "markdown": r"",
                "metadata": {"course_image": {"content": __RESOURCE_ID}},
            },
            {
                "type": CONTENT_TYPE_RESOURCE_LIST,
                "markdown": r"",
                "metadata": {"resources": {"content": [__RESOURCE_ID]}},
            },
        ],
    ],
}
