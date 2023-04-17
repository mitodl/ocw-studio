"""videos signals"""
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from videos.constants import DESTINATION_YOUTUBE
from videos.models import Video, VideoFile
from videos.tasks import delete_s3_objects, remove_youtube_video


@receiver(pre_delete, sender=Video)
def delete_video_transcripts(
    sender, instance: Video, **kwargs
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
def delete_youtube_video(sender, **kwargs):  # pylint:disable=unused-argument
    """
    Call the YouTube API to delete a video
    """
    video_file = kwargs["instance"]
    delete_s3_objects.delay(video_file.s3_key)
    if video_file.destination == DESTINATION_YOUTUBE:
        youtube_id = video_file.destination_id
        if youtube_id is not None:
            remove_youtube_video.delay(youtube_id)
