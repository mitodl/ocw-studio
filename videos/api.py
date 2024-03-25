"""APi functions for video processing"""

import json
import logging
import os

import boto3
import botocore
from django.conf import settings

from content_sync.utils import move_s3_object
from gdrive_sync.models import DriveFile
from gdrive_sync.utils import fetch_content_file_size
from main.s3_utils import get_boto3_resource
from videos.apps import VideoApp
from videos.constants import (
    DESTINATION_ARCHIVE,
    DESTINATION_YOUTUBE,
    VideoFileStatus,
    VideoJobStatus,
    VideoStatus,
)
from videos.models import Video, VideoFile, VideoJob

log = logging.getLogger(__name__)

VIDEO_DOWNLOAD_PATTERN = "_360p_16_9."


def prepare_video_download_file(video: Video):
    """Update the video file and associated resource with correct download url"""
    video_file = VideoFile.objects.filter(
        video=video,
        destination=DESTINATION_ARCHIVE,
        s3_key__contains=VIDEO_DOWNLOAD_PATTERN,
    ).first()
    if not video_file:
        return
    new_s3_key = "/".join(
        [
            f"{video.website.s3_path}",
            f"{video_file.s3_key.split('/')[-1]}",
        ]
    ).strip("/")
    if new_s3_key != video_file.s3_key:
        move_s3_object(video_file.s3_key, new_s3_key)
        video_file.s3_key = new_s3_key
        video_file.save()
    content = DriveFile.objects.get(video=video).resource
    content.file = new_s3_key

    # update file size metadata
    s3 = get_boto3_resource("s3")
    bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME)
    try:
        content.metadata["file_size"] = fetch_content_file_size(content, bucket)
    except botocore.exceptions.ClientError as ex:
        log.exception("Could not read file size for video %s.", video, exc_info=ex)

    content.save()


def create_media_convert_job(video: Video):
    """Create a MediaConvert job for a Video"""
    source_prefix = settings.DRIVE_S3_UPLOAD_PREFIX
    client = boto3.client(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )
    with open(  # noqa: PTH123
        os.path.join(  # noqa: PTH118
            settings.BASE_DIR, f"{VideoApp.name}/config/mediaconvert.json"
        ),  # noqa: PTH118, RUF100
        encoding="utf-8",
    ) as job_template:
        job_dict = json.loads(job_template.read())
        job_dict["UserMetadata"]["filter"] = settings.VIDEO_TRANSCODE_QUEUE
        job_dict["Queue"] = (
            f"arn:aws:mediaconvert:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:queues/{settings.VIDEO_TRANSCODE_QUEUE}"
        )
        job_dict["Role"] = (
            f"arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.AWS_ROLE_NAME}"
        )
        destination = os.path.splitext(  # noqa: PTH122
            video.source_key.replace(
                source_prefix,
                settings.VIDEO_S3_TRANSCODE_PREFIX,
            )
        )[0]
        job_dict["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
            "FileGroupSettings"
        ]["Destination"] = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{destination}"
        job_dict["Settings"]["Inputs"][0][
            "FileInput"
        ] = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{video.source_key}"
        job = client.create_job(**job_dict)
        VideoJob.objects.get_or_create(video=video, job_id=job["Job"]["Id"])
        video.status = VideoStatus.TRANSCODING
        video.save()


def process_video_outputs(video: Video, output_group_details: dict):
    """Create video model objects for each output"""
    for group_detail in output_group_details:
        for output_detail in group_detail.get("outputDetails", []):
            for path in output_detail.get("outputFilePaths", []):
                s3_key = "/".join(path.replace("s3://", "").split("/")[1:])
                basename, _ = os.path.splitext(s3_key)  # noqa: PTH122
                VideoFile.objects.update_or_create(
                    video=video,
                    s3_key=s3_key,
                    defaults={
                        "destination": (
                            DESTINATION_YOUTUBE
                            if basename.endswith("youtube")
                            else DESTINATION_ARCHIVE
                        ),
                        "destination_id": None,
                        "destination_status": None,
                        "status": VideoFileStatus.CREATED,
                    },
                )
    prepare_video_download_file(video)


def update_video_job(video_job: VideoJob, results: dict):
    """Update a VideoJob and associated Video, VideoFiles based on MediaConvert results"""  # noqa: E501
    video_job.job_output = results
    status = results.get("status")
    video = video_job.video
    if status == "COMPLETE":
        video_job.status = VideoJobStatus.COMPLETE
        try:
            process_video_outputs(video, results.get("outputGroupDetails"))
        except:  # pylint:disable=bare-except  # noqa: E722
            log.exception("Error processing video outputs for job %s", video_job.job_id)
    elif status == "ERROR":
        video.status = VideoStatus.FAILED
        video_job.status = VideoJobStatus.FAILED
        log.error(
            "Transcode failure for %s, error code %s: %s",
            video.source_key,
            results.get("errorCode"),
            results.get("errorMessage"),
        )
        video_job.error_code = str(results.get("errorCode"))
        video_job.error_message = results.get("errorMessage")
    video_job.save()
    video.save()
