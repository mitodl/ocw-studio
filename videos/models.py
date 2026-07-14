"""Video models"""

from django.db import models
from django.db.models import CASCADE
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet

from main import settings
from main.utils import get_base_filename, get_file_extension
from videos.constants import (
    CAPTION_FILE_EXTENSIONS,
    DESTINATION_YOUTUBE,
    TRANSCRIPT_FILE_EXTENSIONS,
    VideoFileStatus,
    VideoJobStatus,
    VideoStatus,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig
from websites.utils import get_dict_query_field


class VideoQuerySet(TimestampedModelQuerySet):
    """Queryset for Video"""


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

    def caption_transcript_resources(
        self,
    ) -> tuple[list[WebsiteContent], list[WebsiteContent]]:
        """Search for and return the video's caption resources and transcript resources.

        Returns a 2-tuple of lists: (captions, transcripts).  Each list may
        contain zero, one, or multiple WebsiteContent objects — one per
        language-tagged file discovered in the website.  Candidates are found
        by filename prefix (``{video_filename}_captions`` /
        ``{video_filename}_transcript``) then filtered by the real extension
        of their uploaded file (one of ``CAPTION_FILE_EXTENSIONS`` /
        ``TRANSCRIPT_FILE_EXTENSIONS``). The real file extension is used
        rather than the filename's tail because ``find_available_name`` can
        append a bare digit to a colliding filename (e.g. ``..._vtt`` ->
        ``..._vtt2``), which would defeat an exact suffix match.
        """
        youtube_id = self.youtube_id()

        query_youtube_id_field = get_dict_query_field("metadata", settings.YT_FIELD_ID)
        video_resource = (
            WebsiteContent.objects.filter(website=self.website)
            .filter(models.Q(**{query_youtube_id_field: youtube_id}))
            .first()
        )
        if video_resource:
            video_filename = get_base_filename(video_resource.filename)

            def _matching(prefix, extensions):
                candidates = WebsiteContent.objects.filter(
                    website=self.website, filename__startswith=prefix
                )
                return [
                    r
                    for r in candidates
                    if r.file and get_file_extension(r.file.name) in extensions
                ]

            captions = _matching(f"{video_filename}_captions", CAPTION_FILE_EXTENSIONS)
            transcripts = _matching(
                f"{video_filename}_transcript", TRANSCRIPT_FILE_EXTENSIONS
            )
            return captions, transcripts
        return [], []

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
        """Represent Video as string"""
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
        """Represent VideoFile as string"""
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
        """Represent VideoJob as string"""
        return f"'{self.job_id}' ({self.status})"
