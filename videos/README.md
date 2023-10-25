# Video Workflow

This document describes the components of the video workflow for OCW.

**SECTIONS**

1. [Overview](#overview)
1. [Google Drive Sync and AWS Transcoding](#google-drive-sync-and-aws-transcoding)
1. [YouTube Submission](#youtube-submission)
1. [Captioning and 3Play Transcript Request](#captioning-and-3play-transcript-request)
1. [Completing the Workflow](#completing-the-workflow)
1. [Management Commands](#management-commands)

# Overview

This assumes that [Google Drive sync](/README#enabling-google-drive-integration), [YouTube integration](/README#enabling-youtube-integration), [AWS MediaConvert](/README.md#enabling-aws-transcoding), and [3Play submission](/README.md#enabling-3play-integration) are all enabled, which is required for the video workflow.

The high-level description of the process is below, and each subsequent section contains additional details, including links to the relevant code.

- Upload a video with the name `<video_name>.<video_extension>` to the `videos_final` folder on Google Drive, where `<video_extension>` is a valid video extension, such as `mp4`. If there are pre-existing captions that should be uploaded with the video (as opposed to requesting captions/transcript from 3Play), then these should be named _exactly_ `<video_name>_captions.vtt` and `<video_name>_transcript.pdf`, and uploaded into the `files_final` folder on Google Drive.
- Sync using the Studio UI. This uploads the video to S3.
- As soon as the upload to S3 is complete, Studio initiates a celery task to submit the video to the AWS Media Convert service.
- Once trancoding is complete, the video is uploaded to YouTube (set as unlisted prior to the course being published).
- After the video has been successfully uploaded to YouTube, and if there are no pre-existing captions, Studio sends a transcript request to 3Play.
- Once 3Play completes the transcript job, the captions (`.vtt` format) and transcript (`.pdf` format) are fetched and associated with the video.
- When the course is published, the video metadata and YouTube metadata are updated, and the YouTube video is set to public.

# Google Drive Sync and AWS Transcoding

Users upload videos in a valid video format to the `videos_final` folder. Whether a file is located in this folder is used for defining the `is_video` property defined [here](/gdrive_sync/models.py). The file is processed using the `process_drive_file` function [here](/gdrive_sync/tasks.py), which triggers the `stream_to_s3` and `transcode_gdrive_video` functions [here](/gdrive_sync/api.py), which submit the AWS MediaConvert transcoding job.

The parameters of the AWS transcode request are defined through the AWS interface, and the role is defined [here](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_infrastructure/applications/ocw_studio/__main__.py). Some example JSONs used for triggering MediaConver job are in [this folder](/test_videos_webhook/).

The `TranscodeJobView` endpoint (defined [here](/videos/views.py)) listens for the webhook that is sent when the transcoding job is complete.

# YouTube Submission

Videos are uploaded to YouTube via the `resumable_upload` function, defined [here](/videos/youtube.py).

# Captioning and 3Play Transcript Request

If there are no pre-existing captions, a 3Play transcript request is generated. This is done via the `threeplay_transcript_api_request` function (defined [here](videos/threeplay_api.py)).

# Completing the Workflow

Once the workflow is completed, the `Video` and `WebsiteContent` objects get saved. The only remaining steps are triggered on course publish: updating the video metadata via `update_transcripts_for_website`, defined [here](/videos/tasks.py) and updating the YouTube metadata via `update_youtube_metadata`, defined [here](/videos/youtube.py).

# Management Commands

In cases where something may have gone wrong with the data, often due to legacy data issues, there are management commands that can be run to resolve them. The commands are defined [here](/videos/management/commands/).
