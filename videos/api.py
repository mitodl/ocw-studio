"""APi functions for video processing"""
import json
import logging
import os

import boto3
from django.conf import settings

from videos.apps import VideoApp
from videos.constants import DESTINATION_ARCHIVE, DESTINATION_YOUTUBE, VideoStatus
from videos.models import Video, VideoFile, VideoJob


log = logging.getLogger(__name__)


def create_media_convert_job(video: Video, source_prefix=None):
    """Create a MediaConvert job for a Video"""
    if source_prefix is None:
        source_prefix = settings.DRIVE_S3_UPLOAD_PREFIX
    endpoint = boto3.client(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    ).describe_endpoints()["Endpoints"][0]["Url"]
    client = boto3.client(
        "mediaconvert", region_name=settings.AWS_REGION, endpoint_url=endpoint
    )
    with open(
        os.path.join(settings.BASE_DIR, f"{VideoApp.name}/config/mediaconvert.json"),
        "r",
    ) as job_template:
        job_dict = json.loads(job_template.read())
        job_dict["UserMetadata"]["filter"] = settings.VIDEO_TRANSCODE_QUEUE
        job_dict[
            "Queue"
        ] = f"arn:aws:mediaconvert:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:queues/{settings.VIDEO_TRANSCODE_QUEUE}"
        job_dict[
            "Role"
        ] = f"arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.AWS_ROLE_NAME}"
        destination = os.path.splitext(
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
                basename, _ = os.path.splitext(s3_key)
                VideoFile.objects.update_or_create(
                    video=video,
                    s3_key=s3_key,
                    defaults={
                        "destination": DESTINATION_YOUTUBE
                        if basename.endswith("youtube")
                        else DESTINATION_ARCHIVE,
                        "destination_id": None,
                        "destination_status": None,
                    },
                )


def update_video_job(video_job: VideoJob, results: dict):
    """Update a VideoJob and associated Video, VideoFiles based on MediaConvert results"""
    status = results.get("status")
    video = video_job.video
    if status == "COMPLETE":
        process_video_outputs(video, results.get("outputGroupDetails"))
        # future PR: upload to youtube & internet archive, create WebsiteContent for video
    elif status == "ERROR":
        video.status = VideoStatus.FAILED
        log.error(
            "Transcode failure for %s, error code %s: %s",
            video.source_key,
            results.get("errorCode"),
            results.get("errorMessage"),
        )
        video_job.error_code = str(results.get("errorCode"))
        video_job.error_message = results.get("errorMessage")
    video_job.status = status
    video_job.save()
    video.save()
