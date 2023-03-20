"""Management command to sync captions and transcripts for any videos missing them from 3play API"""
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.core.management import BaseCommand
from django.db.models import Q

from main.utils import get_dirpath_and_filename, get_file_extension
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from websites.models import WebsiteContent


class Command(BaseCommand):
    """Check for WebContent with missing caption/transcripts, and syncs via 3play API"""

    help = __doc__

    def __init__(self):
        super().__init__()
        self.transcript_base_url = (
            "https://static.3playmedia.com/p/files/{media_file_id}/threeplay_transcripts/"
            "{transcript_id}?project_id={project_id}"
        )

    def handle(self, *args, **options):
        content_videos = WebsiteContent.objects.filter(
            Q(metadata__resourcetype="Video")
            & (
                Q(metadata__video_files__video_captions_file=None)
                | Q(metadata__video_files__video_transcript_file=None)
            )
        )

        for video in content_videos:
            youtube_id = video.metadata["video_metadata"]["youtube_id"]

            new_captions_obj = self.create_new_captions(video, youtube_id)
            video.metadata["video_files"]["video_captions_file"] = str(
                new_captions_obj.file
            )
            video.save()

    def create_new_captions(self, video, youtube_id):
        """Fetches and Creates new caption/ Transcript using 3play API"""
        threeplay_transcript_json = threeplay_transcript_api_request(youtube_id)

        if (
            threeplay_transcript_json.get("data")
            and len(threeplay_transcript_json.get("data")) > 0
            and threeplay_transcript_json.get("data")[0].get("status") == "complete"
        ):
            transcript_id = threeplay_transcript_json["data"][0].get("id")
            media_file_id = threeplay_transcript_json["data"][0].get("media_file_id")

            url = self.transcript_base_url.format(
                media_file_id, transcript_id, settings.THREEPLAY_PROJECT_ID
            )
            pdf_url = url + "&format_id=46"
            pdf_response = fetch_file(pdf_url)

            if pdf_response:
                pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
                self.create_new_content(pdf_file, video, youtube_id)

            url = self.transcript_base_url.format(
                media_file_id, transcript_id, settings.THREEPLAY_PROJECT_ID
            )
            webvtt_url = url + "&format_id=51"
            webvtt_response = fetch_file(webvtt_url)

            if webvtt_response:
                vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
                self.create_new_content(vtt_file, video, youtube_id)

            video.save()
            return True

        return False

    def generate_metadata(self, youtube_id, new_uid, new_s3_path, file_content):
        """Generate new metadata for new VTT WebsiteContent object"""
        file_ext = get_file_extension(file_content)
        title = "3play caption file"
        file_type = "application/x-subrip"
        resource_type = "Other"

        if file_ext == "pdf":
            title = "3play transcript file"
            file_type = "application/pdf"
            resource_type = "Document"

        return (
            title,
            {
                "uid": new_uid,
                "file": new_s3_path,
                "title": title,
                "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "ocw_type": "OCWFile",
                "file_type": file_type,
                "description": "",
                "video_files": {"video_thumbnail_file": None},
                "resourcetype": resource_type,
                "video_metadata": {"youtube_id": youtube_id},
                "learning_resource_types": [],
            },
        )

    def generate_s3_path(self, file_content, video):
        """Generates S3 path for the file"""
        _, new_filename = get_dirpath_and_filename(file_content.name)
        new_filename_ext = get_file_extension(file_content.name)

        if new_filename_ext == "webvtt":
            new_filename += "_captions"
        elif new_filename_ext == "pdf":
            new_filename += "_transcript"

        new_s3_path = f"/{video.website.s3_path.rstrip('/').lstrip('/')}/{new_filename.lstrip('/')}.{new_filename_ext}"

        return new_s3_path

    def create_new_content(self, file_content, video, youtube_id):
        """Create new WebsiteContent object for caption or transcript using 3play response"""
        new_text_id = str(uuid4())
        new_s3_loc = self.generate_s3_path(file_content, video)
        title, new_obj_metadata = self.generate_metadata(
            youtube_id, new_text_id, new_s3_loc, file_content
        )
        new_obj = WebsiteContent.objects.get_or_create(
            website=video.website,
            text_id=new_text_id,
            defaults={
                "metadata": new_obj_metadata,
                "title": title,
                "type": "resource",
                "file": file_content,
                "dirpath": get_dirpath_and_filename(new_s3_loc)[0],
                "filename": get_dirpath_and_filename(new_s3_loc)[1],
                "is_page_content": True,
            },
        )[0]
        new_obj.save()

        return new_obj
