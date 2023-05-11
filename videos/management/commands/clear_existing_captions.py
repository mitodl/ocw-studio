"""Management command to sync captions and transcripts for any videos missing them from 3play API"""

from django.db.models import Q
from safedelete.models import HARD_DELETE

from main.management.commands.filter import WebsiteFilterCommand
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.models import WebsiteContent
from websites.utils import set_dict_field

class Command(WebsiteFilterCommand):
    """Nullifies and deletes existing captions and transcripts for provided courses"""

    help = __doc__

    def handle(self, *args, **options):
        super().handle(*args, **options)

        all_content = WebsiteContent.objects.all()
        
        if not self.filter_list:
            self.stdout.write('This command can only be used with a filter list.')
            exit(1)
            
        website_contents = self.filter_website_contents(all_content)
        
        captions_transcripts = website_contents.filter(
            Q(filename__icontains="_captions") | Q(filename__icontains="_transcript")
        )
        videos = website_contents.filter(
            Q(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
        )

        captions_transcripts.delete(HARD_DELETE)

        for video in videos:
            set_dict_field(video.metadata, "video_files.video_captions_file", None)
            set_dict_field(video.metadata, "video_files.video_transcript_file", None)
            video.save()
            
            self.stdout.write(f'Captions and transcripts file data has been cleared for following:\nVideo: {video.title}\nWebsite: {video.website.title}')
