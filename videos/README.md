# Video Workflow

This document describes the components of the video workflow for OCW.

**SECTIONS**

1. [Overview](#overview)
1. [Google Drive Sync and AWS Transcoding](#google-drive-sync-and-aws-transcoding)
1. [YouTube Submission](#youtube-submission)
1. [Captioning and 3Play Transcript Request](#captioning-and-3play-transcript-request)
1. [Completing the Workflow](#completing-the-workflow)
1. [Management Commands](#management-commands)
1. [Testing PRs with Transcoding](#testing-prs-with-transcoding)
1. [Adding Captions and Transcript to Existing Videos](#adding-captions-and-transcript-to-existing-videos)

# Overview

This assumes that [Google Drive sync](/README.md#enabling-google-drive-integration), [YouTube integration](/README.md#enabling-youtube-integration), [AWS MediaConvert](/README.md#enabling-aws-transcoding), and [3Play submission](/README.md#enabling-3play-integration) are all enabled, which is required for the video workflow.

The high-level description of the process is below, and each subsequent section contains additional details, including links to the relevant code.

- Browse to a course site in the Studio UI, go to the Resources page and click the icon to the right of the `Sync w/ Google Drive` button to open the site's Google Drive folder in the Google Drive UI.
- Upload a video with the name `<video_name>.<video_extension>` to the `videos_final` folder on Google Drive, where `<video_extension>` is a valid video extension, such as `mp4`. If there are pre-existing captions that should be uploaded with the video (as opposed to requesting captions/transcript from 3Play), then these should be named _exactly_ `<video_name>_captions.vtt` and `<video_name>_transcript.pdf`, and uploaded into the `files_final` folder on Google Drive.
- Sync using the Studio UI. This uploads the video to S3.
- As soon as the upload to S3 is complete, Studio initiates a celery task to submit the video to the AWS Media Convert service.
- Once trancoding is complete, the video is uploaded to YouTube (set as unlisted prior to the course being published).
- After the video has been successfully uploaded to YouTube, and if there are no pre-existing captions, Studio sends a transcript request to 3Play.
- Once 3Play completes the transcript job, the captions (`.vtt` format) and transcript (`.pdf` format) are fetched and associated with the video.
- On any publish action, the video metadata and YouTube metadata are updated, assuming the information has been received from the external services.
- The YouTube video is set to public once the course has been published to live/production.

# Google Drive Sync and AWS Transcoding

Users upload videos in a valid video format to the `videos_final` folder. Whether a file is located in this folder is used for defining the [is_video property](/gdrive_sync/models.py). The file is processed using the [process_drive_file function](/gdrive_sync/tasks.py), which triggers the [`stream_to_s3` and `transcode_gdrive_video` functions](/gdrive_sync/api.py), which submit the AWS MediaConvert transcoding job.

The parameters of the AWS transcode request are defined through the AWS interface, and the role is defined [here](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_infrastructure/applications/ocw_studio/__main__.py). Some example JSONs used for triggering MediaConvert job are in [this folder](/test_videos_webhook/).

The [`TranscodeJobView` endpoint](/videos/views.py) listens for the webhook that is sent when the transcoding job is complete.

# YouTube Submission

Videos are uploaded to YouTube via the [`resumable_upload` function](/videos/youtube.py). The [YouTube upload success notification](/videos/templates/mail/youtube_upload_success/body.html) is sent by email when the [`update_youtube_statuses`](/videos/tasks.py) task is complete; exceptions in this task trigger the [YouTube upload failure notification](/videos/templates/mail/youtube_upload_failure/body.html). When the course is published to draft/staging, the video is set to `unlisted`. However, when it is published to live/production, the video is made public on YouTube, via the [`update_youtube_metadata` function](/videos/youtube.py). When a video is made public on YouTube, all YouTube subscribers will be notified. There are nearly 5 million subscribers to the OCW YouTube channel, so be careful with this setting. Subsequently republishing the course to draft/staging will not change the visibility of the YouTube video. However, if the video resource is set to "Draft" and the course is republished, the video will again be set to `unlisted`.

## Enabling YouTube Metadata Updates

The PostHog feature flag `FEATURE_FLAG_ENABLE_YOUTUBE_UPDATE` (defined in [`main/feature_flags.py`](/main/feature_flags.py)) controls whether automatic YouTube metadata updates occur during publish. **By default, YouTube updates are disabled** unless this flag is enabled.

**Default Behavior (Flag Not Set or False):**

- YouTube metadata updates are **disabled**
- Videos are uploaded but metadata (title, description, visibility) is **not** updated
- No YouTube subscriber notifications are triggered

**When Flag is Enabled (Set to True in PostHog):**

- YouTube metadata updates proceed normally
- Video visibility, titles, and descriptions are updated
- YouTube subscribers may receive notifications when videos are made public

To enable YouTube updates in PostHog, set `OCW_STUDIO_ENABLE_YOUTUBE_UPDATE` to `true` for the desired user group or rollout percentage.

## Testing YouTube Updates on RC/Staging

For testing YouTube metadata updates on RC or staging environments without affecting production videos, set `YT_TEST_VIDEO_IDS` in your `.env` file to a comma-separated list of YouTube video IDs:

```bash
YT_TEST_VIDEO_IDS=abc123,def456,ghi789
```

**Important:** Videos in this list will **bypass the PostHog feature flag** (`FEATURE_FLAG_ENABLE_YOUTUBE_UPDATE`) and always have their metadata updated, even when the flag is not enabled. This is useful for:

- Testing YouTube integration changes with specific test videos on RC while the flag is disabled (default)
- Safe testing on RC/staging without enabling updates for all videos

When `YT_TEST_VIDEO_IDS` is configured:

- Videos with IDs **in the list**: Always updated (bypasses feature flag check entirely)
- Videos with IDs **not in the list**: Updates disabled unless feature flag is enabled

# Captioning and 3Play Transcript Request

If there are no pre-existing captions, a 3Play transcript request is generated. This is done via the [`threeplay_transcript_api_request` function](/videos/threeplay_api.py).

# Completing the Workflow

Once the workflow is completed, the updates to the `Video` and `WebsiteContent` objects are nearly complete. The only remaining steps are triggered on course publish: updating the video metadata via [`update_transcripts_for_website`](/videos/tasks.py) and updating the YouTube metadata via [`update_youtube_metadata`](/videos/youtube.py).

# Management Commands

In cases where something may have gone wrong with the data, often due to legacy data issues, there are management commands that can be run to resolve them. The commands are defined [here](/videos/management/commands/). These commands are:

- [backpopulate_video_downloads](/videos/management/commands/backpopulate_video_downloads.py) In the existing video workflow, the MediaConvert job creates a downloadable verion as well as the YouTube version. Initially, these downloadable versions were not in the same S3 path as the course site's other resource content, and running this command moves them to the appropriate location.
- [clear_webvtt_files](/videos/management/commands/clear_webvtt_files.py) Some captions were initially saved without an extension; this management command deletes them from S3 and clears the resource metadata, allowing them to be re-created.
- [sync_missing_captions](/videos/management/commands/sync_missing_captions.py) This management command syncs captions and transcripts from 3Play to course videos missing them.
- [sync_transcripts](/videos/management/commands/sync_transcripts.py). This management command syncs captions and transcripts for any videos missing them from one course (`from_course`) to another (`to_course`).

# Testing PRs with Transcoding

Before working on, testing, or reviewing any PR that requires a video to be uploaded to YouTube, make sure that AWS buckets (instead of local Minio storage) are being used for testing. To do that, set `OCW_STUDIO_ENVIRONMENT` to any value other than `dev`.

Set the following variables to the same values as for RC:

```
AWS_ACCOUNT_ID
AWS_ACCESS_KEY_ID
AWS_REGION
AWS_ROLE_NAME
AWS_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME
DRIVE_SERVICE_ACCOUNT_CREDS
DRIVE_SHARED_ID
VIDEO_S3_TRANSCODE_ENDPOINT
VIDEO_S3_TRANSCODE_PREFIX
```

Upload the video to the course's Google Drive folder, as described in the [Google Drive Sync and AWS Transcoding](#google-drive-sync-and-aws-transcoding) section above. Wait for the video transcoding job to complete, which requires an amount of time proportional to the length of the video; for a very short video, this should only take a few minutes.

Next, the response to the transcode request needs to be simulated. This is because the AWS MediaConvert service will not send a webhook notification to the local OCW Studio instance, but rather to the RC URL.

To simulate the response, use cURL, Postman, or an equivalent tool to POST a message to `https://localhost:8043/api/transcode-jobs/`, with the body as in the example below, updated to match the relevant environment variables, course name, and video name.

```json
{
  "version": "0",
  "id": "c120fe11-87db-c292-b3e5-1cc90740f6e1",
  "detail-type": "MediaConvert Job State Change",
  "source": "aws.mediaconvert",
  "account": "<settings.AWS_ACCOUNT_ID>",
  "detail": {
    "timestamp": 1629911639065,
    "accountId": "<settings.AWS_ACCOUNT_ID>",
    "queue": "arn:aws:mediaconvert:us-east-1:919801701561:queues/Default",
    "jobId": "<VideoJob.job_id>",
    "status": "COMPLETE",
    "userMetadata": {},
    "outputGroupDetails": [
      {
        "outputDetails": [
          {
            "outputFilePaths": [
              "s3://<settings.AWS_STORAGE_BUCKET_NAME>/aws_mediaconvert_transcodes/<Website.short_id>/<DriveFile.file_id>/<original_video_filename_base>_youtube.mp4"
            ],
            "durationInMs": 45466,
            "videoDetails": {
              "widthInPx": 320,
              "heightInPx": 176
            }
          },
          {
            "outputFilePaths": [
              "s3://<settings.AWS_STORAGE_BUCKET_NAME>/aws_mediaconvert_transcodes/<Website.short_id>/<DriveFile.file_id>/<original_video_filename_base>_360p_16_9.mp4"
            ],
            "durationInMs": 45466,
            "videoDetails": {
              "widthInPx": 640,
              "heightInPx": 360
            }
          },
          {
            "outputFilePaths": [
              "s3://<settings.AWS_STORAGE_BUCKET_NAME>/aws_mediaconvert_transcodes/<Website.short_id>/<DriveFile.file_id>/<original_video_filename_base>_360p_4_3.mp4"
            ],
            "durationInMs": 45466,
            "videoDetails": {
              "widthInPx": 480,
              "heightInPx": 360
            }
          }
        ],
        "type": "FILE_GROUP"
      }
    ]
  }
}
```

making sure to set the values in `<>`. In particular, set

```
<settings.AWS_ACCOUNT_ID>
<VideoJob.job_id>
<settings.AWS_STORAGE_BUCKET_NAME>/aws_mediaconvert_transcodes/<Website.short_id>/<DriveFile.file_id>/<original_video_filename_base>
```

The `DriveFile` will be the one associated with the video: http://localhost:8043/admin/gdrive_sync/drivefile/.

If this completes successfully, the `VideoJob` status in Django admin should be `COMPLETE`, and there should now be three new `VideoFile` objects populated with `status`, `destination`, and `s3_key` fields.

# Adding Captions and Transcript to Existing Videos

Existing caption (`.vtt`) and transcript (`.pdf`) resources can be associated with a video resource directly in OCW Studio without requiring a new upload or 3Play transcript request.

The `Edit Resource` form includes two fields: `Video Captions Resource` and `Video Transcript Resource`. These fields can be used to select resources that contain the corresponding caption and transcript files. _The files associated with the resources are not required to follow the `_captions.vtt` and `_transcript.pdf` naming convention used by Google Drive sync._

When the video resource is saved, the serializer updates the `Video Captions (WebVTT) URL` and `Video Transcript (PDF) URL` fields based on the selected resources. Either field may be populated independently, and existing associations can be cleared by removing the selected resource (by clicking on the `X`) and saving the video resource again.

The site configuration metadata fields for these associations are defined by the environment variables `YT_FIELD_CAPTIONS_RESOURCE` and `YT_FIELD_TRANSCRIPT_RESOURCE`.

On course publish, the associated captions and transcript files are included in the site output and propagated to YouTube metadata as part of the standard publish process.
