"""Management command to sync captions and transcripts for any videos missing them from 3play API"""
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.core.management import BaseCommand
from django.db.models import Q

from main.utils import get_dirpath_and_filename, get_file_extension
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from videos.utils import generate_s3_path
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
        self.extension_map = {
            "vtt": {
                "ext": "captions",
                "file_type": "application/x-subrip",
                "resource_type": "Other",
            },
            "webvtt": {
                "ext": "captions",
                "file_type": "application/x-subrip",
                "resource_type": "Other",
            },
            "pdf": {
                "ext": "transcript",
                "file_type": "application/pdf",
                "resource_type": "Document",
            },
        }

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
            self.stdout.write(
                f"[*] Parsing\nCourse: {video.website}\nVideo: {video.title}"
            )
            self.fetch_and_update_content(video, youtube_id)

    def fetch_and_update_content(self, video, youtube_id):
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
                media_file_id=media_file_id, transcript_id=transcript_id, project_id=2
            )
            pdf_url = url + "&format_id=46"
            pdf_response = fetch_file(pdf_url)

            if pdf_response:
                pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
                new_filepath = self.create_new_content(pdf_file, video)
                video.metadata["video_files"]["video_transcript_file"] = new_filepath

            url = self.transcript_base_url.format(
                media_file_id=media_file_id, transcript_id=transcript_id, project_id=2
            )
            webvtt_url = url + "&format_id=51"
            webvtt_response = fetch_file(webvtt_url)

            if webvtt_response:
                vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
                new_filepath = self.create_new_content(vtt_file, video)
                video.metadata["video_files"]["video_captions_file"] = new_filepath

            self.stdout.write(
                f"[!] Captions and Transcripts Updated!\nCourse: {video.website}\nVideo: {video.title}"
            )
            video.save()

    def generate_metadata(self, new_uid, new_s3_path, file_content, video):
        """Generate new metadata for new VTT WebsiteContent object"""
        file_ext = self.extension_map[get_file_extension(str(file_content))]
        title = f"{video.title} {file_ext['ext']}"
        youtube_id = video.metadata["video_metadata"]["youtube_id"]

        return (
            title,
            {
                "uid": new_uid,
                "file": new_s3_path,
                "title": title,
                "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "ocw_type": "OCWFile",
                "file_type": file_ext["file_type"],
                "description": "",
                "video_files": {"video_thumbnail_file": None},
                "resourcetype": file_ext["resource_type"],
                "video_metadata": {"youtube_id": youtube_id},
                "learning_resource_types": [],
            },
        )

    def create_new_content(self, file_content, video):
        """Create new WebsiteContent object for caption or transcript using 3play response"""
        new_text_id = str(uuid4())
        new_s3_loc = generate_s3_path(file_content, video.website)
        title, new_obj_metadata = self.generate_metadata(
            new_text_id, new_s3_loc, file_content, video
        )
        dirpath, filename = get_dirpath_and_filename(new_s3_loc)

        defaults = {
            "metadata": new_obj_metadata,
            "title": title,
            "type": "resource",
            "file": file_content,
            "text_id": new_text_id,
        }

        new_obj = WebsiteContent.objects.get_or_create(
            website=video.website,
            filename=filename,
            dirpath=dirpath,
            is_page_content=True,
            defaults=defaults,
        )[0]
        new_obj.save()

        return new_s3_loc
