"""Management command to sync captions and transcripts for any videos missing them from 3play API"""
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.db.models import Q

from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename, get_file_extension
from videos.constants import PDF_FORMAT_ID, WEBVTT_FORMAT_ID
from videos.threeplay_api import fetch_file, threeplay_transcript_api_request
from videos.utils import generate_s3_path
from websites.models import WebsiteContent


class Command(WebsiteFilterCommand):
    """Check for WebContent with missing caption/transcripts, and syncs via 3play API"""

    help = __doc__

    def __init__(self):
        super().__init__()
        self.transcript_base_url = (
            "https://static.3playmedia.com/p/files/{media_file_id}/threeplay_transcripts/"
            "{transcript_id}?project_id={project_id}"
        )

        self.missing_results = 0
        summary_boilerplate = {
            "total": 0,
            "missing": 0,
            "updated": 0,
            "missing_details": [],
        }
        self.summary = {
            "captions": summary_boilerplate.copy(),
            "transcripts": summary_boilerplate.copy(),
        }

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
        super().handle(*args, **options)

        content_videos = WebsiteContent.objects.filter(
            Q(metadata__resourcetype="Video")
            & (
                Q(metadata__video_files__video_captions_file=None)
                | Q(metadata__video_files__video_transcript_file=None)
            )
        )
        if self.filter_list:
            content_videos = self.filter_website_contents(content_videos)

        if not content_videos:
            self.stdout.write("No courses found")
            return

        for video in content_videos:
            youtube_id = video.metadata["video_metadata"]["youtube_id"]
            self.fetch_and_update_content(video, youtube_id)

        for item_type, details in self.summary.items():
            self.stdout.write(
                f"Updated {details['updated']}/{details['total']} {item_type}, missing ({details['missing']}) details are listed below,"
            )
            for youtube_id, course in details["missing_details"]:
                self.stdout.write(f"{youtube_id} of course {course}")

        self.stdout.write(
            f"\nCaptions: {self.summary['captions']['updated']} updated, {self.summary['captions']['missing']} missing, {self.summary['captions']['total']} total\n"
            f"Transcripts: {self.summary['transcripts']['updated']} updated, {self.summary['transcripts']['missing']} missing, {self.summary['transcripts']['total']} total\n"
            f"Found captions or transcripts for {len(content_videos) - self.missing_results}/{len(content_videos)} videos"
        )

    def fetch_and_update_content(self, video, youtube_id):
        """Fetches captions/transcripts and creates new WebsiteContent object using 3play API"""
        threeplay_transcript_json = threeplay_transcript_api_request(youtube_id)

        if (
            not threeplay_transcript_json.get("data")
            or len(threeplay_transcript_json.get("data")) == 0
            or threeplay_transcript_json.get("data")[0].get("status") != "complete"
        ):
            self.missing_results += 1
            self.stdout.write(
                f"Captions and transcripts not found in 3play for video, {video.title} and course {video.website.short_id}"
            )
            return

        transcript_id = threeplay_transcript_json["data"][0].get("id")
        media_file_id = threeplay_transcript_json["data"][0].get("media_file_id")

        # If transcript does not exist
        if not video.metadata["video_files"]["video_transcript_file"]:
            url = self.transcript_base_url.format(
                media_file_id=media_file_id,
                transcript_id=transcript_id,
                project_id=settings.THREEPLAY_PROJECT_ID,
            )
            pdf_url = url + f"&format_id={PDF_FORMAT_ID}"
            pdf_response = fetch_file(pdf_url)
            self.summary["transcripts"]["total"] += 1

            if pdf_response:
                pdf_file = File(pdf_response, name=f"{youtube_id}.pdf")
                new_filepath = self.create_new_content(pdf_file, video)
                video.metadata["video_files"]["video_transcript_file"] = new_filepath
                self.summary["transcripts"]["updated"] += 1
                self.stdout.write(
                    f"Transcript updated for video, {video.title} and course {video.website.short_id}"
                )
            else:
                self.summary["transcripts"]["missing"] += 1
                self.summary["transcripts"]["missing_details"].append(
                    (youtube_id, video.website.short_id)
                )

        # If captions does not exist
        if not video.metadata["video_files"]["video_captions_file"]:
            url = self.transcript_base_url.format(
                media_file_id=media_file_id,
                transcript_id=transcript_id,
                project_id=settings.THREEPLAY_PROJECT_ID,
            )
            webvtt_url = url + f"&format_id={WEBVTT_FORMAT_ID}"
            webvtt_response = fetch_file(webvtt_url)
            self.summary["captions"]["total"] += 1

            if webvtt_response:
                vtt_file = File(webvtt_response, name=f"{youtube_id}.webvtt")
                new_filepath = self.create_new_content(vtt_file, video)
                video.metadata["video_files"]["video_captions_file"] = new_filepath
                self.summary["captions"]["updated"] += 1
                self.stdout.write(
                    f"Captions updated for video, {video.title} and course {video.website.short_id}"
                )
            else:
                self.summary["captions"]["missing"] += 1
                self.summary["captions"]["missing_details"].append(
                    (youtube_id, video.website.short_id)
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

    def upload_to_s3(self, file_content, video):
        """Uploads the captions/transcript file to the S3 bucket"""
        s3 = get_boto3_resource("s3")
        new_s3_loc = generate_s3_path(file_content, video.website)
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_s3_loc).upload_fileobj(
            file_content
        )

        return f"/{new_s3_loc}"

    def create_new_content(self, file_content, video):
        """Create new WebsiteContent object for caption or transcript using 3play response"""
        new_text_id = str(uuid4())
        new_s3_loc = self.upload_to_s3(file_content, video)
        title, new_obj_metadata = self.generate_metadata(
            new_text_id, new_s3_loc, file_content, video
        )
        filename = get_dirpath_and_filename(new_s3_loc)[1]

        defaults = {
            "metadata": new_obj_metadata,
            "title": title,
            "type": "resource",
            "text_id": new_text_id,
        }

        new_obj = WebsiteContent.objects.get_or_create(
            website=video.website,
            filename=filename,
            dirpath="content/resources",
            is_page_content=True,
            defaults=defaults,
        )[0]
        new_obj.save()

        return new_s3_loc
