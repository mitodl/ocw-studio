"""Common functions and variables for gdrive_sync tests"""

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
                "name": "test_document.doc",
                "mimeType": "application/ms-word",
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
