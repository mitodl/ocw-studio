"""Video models"""

from django.db import models
from django.db.models import CASCADE
from mitol.common.models import TimestampedModel

from main import settings
from main.utils import get_file_extension
from videos.constants import (
    DESTINATION_YOUTUBE,
    VideoFileStatus,
    VideoJobStatus,
    VideoStatus,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig
from websites.utils import get_dict_query_field


class Video(TimestampedModel):
    """Video object"""

    def upload_file_to(self, filename):
        """Return the appropriate filepath for an upload"""
        site_config = SiteConfig(self.website.starter.config)
        source_folder = self.source_key.split("/")[-2]

        url_parts = [
            site_config.root_url_path,
            self.website.name,
            f"{source_folder}_{filename}",
        ]
        return "/".join([part for part in url_parts if part != ""])

    def youtube_id(self):
        """Returns destination_id of youtube VideoFile object"""  # noqa: D401
        youtube_videofile = self.videofiles.filter(
            destination=DESTINATION_YOUTUBE
        ).first()
        if youtube_videofile:
            return youtube_videofile.destination_id
        else:
            return None

    def caption_transcript_resources(self) -> tuple[WebsiteContent, WebsiteContent]:
        """Search for and return the video's caption resource and transcript resource if either exists"""  # noqa: E501
        youtube_id = self.youtube_id()

        query_youtube_id_field = get_dict_query_field("metadata", settings.YT_FIELD_ID)
        video_resource = (
            WebsiteContent.objects.filter(website=self.website)
            .filter(models.Q(**{query_youtube_id_field: youtube_id}))
            .first()
        )
        if video_resource:
            video_filename = video_resource.filename
            captions = WebsiteContent.objects.filter(
                models.Q(website=self.website)
                & models.Q(filename=f"{video_filename}_captions")
            )
            captions = [
                caption
                for caption in captions
                if get_file_extension(str(caption.file)) in {"vtt", "webvtt"}
            ]
            captions = captions[0] if captions else None
            transcript = WebsiteContent.objects.filter(
                models.Q(website=self.website)
                & models.Q(filename=f"{video_filename}_transcript")
            ).first()
            return captions, transcript
        return None, None

    source_key = models.CharField(max_length=2048, unique=True)
    website = models.ForeignKey(Website, on_delete=CASCADE, related_name="videos")
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoStatus.CREATED
    )
    pdf_transcript_file = models.FileField(
        upload_to=upload_file_to, editable=True, null=True, blank=True, max_length=2048
    )
    webvtt_transcript_file = models.FileField(
        upload_to=upload_file_to, editable=True, null=True, blank=True, max_length=2048
    )

    def __str__(self):
        return f"'{self.source_key}' ({self.status})"


class VideoFile(TimestampedModel):
    """Video file created by AWS MediaConvert"""

    video = models.ForeignKey(Video, on_delete=CASCADE, related_name="videofiles")
    s3_key = models.CharField(null=False, blank=False, max_length=2048, unique=True)
    destination = models.CharField(blank=False, null=False, max_length=48)
    destination_id = models.CharField(  # noqa: DJ001
        max_length=256, null=True, blank=True
    )
    destination_status = models.CharField(  # noqa: DJ001
        max_length=50, null=True, blank=True
    )
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoFileStatus.CREATED
    )

    def __str__(self):
        return f"'{self.s3_key}' ({self.destination} {self.destination_id})"


class VideoJob(TimestampedModel):
    """MediaConvert job id per video"""

    job_id = models.CharField(max_length=50, primary_key=True)
    video = models.ForeignKey(Video, on_delete=CASCADE)
    error_code = models.CharField(max_length=24, null=True, blank=True)  # noqa: DJ001
    error_message = models.TextField(null=True, blank=True)  # noqa: DJ001
    status = models.CharField(
        max_length=50, null=False, blank=False, default=VideoJobStatus.CREATED
    )
    job_output = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"'{self.job_id}' ({self.status})"
