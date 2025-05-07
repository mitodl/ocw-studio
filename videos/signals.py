"""videos signals"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from videos.models import Video, VideoFile
from videos.tasks import delete_s3_objects
from videos.threeplay_sync import sync_video_captions_and_transcripts
from websites.models import WebsiteContent


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


_ALREADY_PROCESSED = set()


@receiver(post_save, sender=WebsiteContent)
def sync_missing_caption(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):  # pylint:disable=unused-argument
    """
    Sync missing captions and transcripts for video resource (WebsiteContent).
    """
    if instance.pk in _ALREADY_PROCESSED:
        _ALREADY_PROCESSED.remove(instance.pk)
        return
    metadata = instance.metadata or {}
    video_metadata = metadata.get("video_metadata", {})
    if (
        metadata.get("resourcetype") == "Video"
        and video_metadata.get("source") == "youtube"
    ):
        _ALREADY_PROCESSED.add(instance.pk)
        sync_video_captions_and_transcripts(instance)
