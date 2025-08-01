"""videos signals"""

import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from videos.models import Video, VideoFile
from videos.tasks import delete_s3_objects
from videos.threeplay_sync import sync_video_captions_and_transcripts
from websites.models import WebsiteContent

log = logging.getLogger(__name__)


@receiver(pre_delete, sender=Video)
def delete_video_transcripts(
    sender,  # noqa: ARG001
    instance: Video,
    **kwargs,  # noqa: ARG001
):  # pylint:disable=unused-argument
    """
    Delete transcript files.
    """
    if instance.pdf_transcript_file:
        instance.pdf_transcript_file.delete()
        instance.pdf_transcript_file = None

    if instance.webvtt_transcript_file:
        instance.webvtt_transcript_file.delete()
        instance.webvtt_transcript_file = None


@receiver(pre_delete, sender=VideoFile)
def delete_video_file_objects(
    sender,  # noqa: ARG001
    **kwargs,
):  # pylint:disable=unused-argument
    """
    Delete S3 objects for the video file.
    """
    video_file = kwargs["instance"]
    delete_s3_objects.delay(video_file.s3_key)


@receiver(post_save, sender=WebsiteContent)
def sync_missing_caption(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):  # pylint:disable=unused-argument
    """
    Sync missing captions and transcripts for video resource (WebsiteContent).
    """
    # Prevent recursion
    if getattr(instance, "skip_sync", False):
        return

    metadata = instance.metadata or {}
    video_metadata = metadata.get("video_metadata", {})
    if (
        metadata.get("resourcetype") == "Video"
        and video_metadata.get("source") == "youtube"
    ):
        if archive_url := metadata.get("video_files", {}).get("archive_url"):
            log.info(
                "Populating file size for video %s with archive_url %s",
                instance.id,
                archive_url,
            )
        else:
            log.warning(
                "No archive_url found for video %s, cannot populate file size",
                instance.id,
            )
            instance.metadata = metadata
            metadata["file_size"] = None
            instance.skip_sync = True
            instance.save(update_fields=["metadata"])
        sync_video_captions_and_transcripts(instance)
