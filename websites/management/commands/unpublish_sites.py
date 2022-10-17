"""Unpublish course webpages provided to the command that have no dependencies. If there are dependencies, print the dependencies."""
import json

from django.conf import settings
from django.db.models import Q

from content_sync.api import trigger_unpublished_removal
from main.management.commands.filter import WebsiteFilterCommand
from users.models import User
from websites.constants import (
    CONTENT_TYPE_COURSE_LIST,
    CONTENT_TYPE_PAGE,
    CONTENT_TYPE_RESOURCE_COLLECTION,
    PUBLISH_STATUS_NOT_STARTED,
)
from websites.models import Website, WebsiteContent
from websites.serializers import WebsiteBasicSerializer, WebsiteContentSerializer


class Command(WebsiteFilterCommand):
    """Unpublish course webpages provided to the command that have no dependencies. If there are dependencies, print the dependencies."""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--course-ids",
            nargs="+",
            dest="course_ids",
            help="List of course webpages to be unpublished",
        )

        parser.add_argument(
            "--user",
            dest="user",
            help="Username (email address) for unpublishing courses",
        )

    def check_email(self, email_id):
        try:
            user = User.objects.get(email__exact=email_id)
            return user
        except User.DoesNotExist:
            return None

    def handle(self, *args, **options):
        super().handle(*args, **options)
        if not options["course_ids"]:
            self.stdout.write("Please provide a list of course ids to unpublish.")
        elif not options["user"]:
            self.stdout.write("Please provide a username to unpublish courses.")
        elif not self.check_email(options["user"]):
            self.stdout.write(
                "Please provide a valid username (email address) to unpublish courses."
            )
        else:
            user_id = self.check_email(options["user"])
            websites = Website.objects.filter(name__in=options["course_ids"])
            for website in websites:
                ocw_www_dependencies = WebsiteContent.objects.filter(
                    (
                        Q(type=CONTENT_TYPE_COURSE_LIST)
                        | Q(type=CONTENT_TYPE_RESOURCE_COLLECTION)
                    ),
                    (
                        Q(metadata__courses__icontains=website.name)
                        | Q(metadata__resources__content__icontains=website.name)
                    ),
                    website__name=settings.ROOT_WEBSITE_NAME,
                )
                course_content_dependencies = WebsiteContent.objects.filter(
                    ~Q(website__name=website.name),
                    type=CONTENT_TYPE_PAGE,
                    markdown__icontains=website.name,
                )
                course_dependencies = Website.objects.filter(
                    ~Q(name=website.name), metadata__icontains=website.name
                )
                # if there are dependencies, don't unpublish and list dependencies
                if (
                    ocw_www_dependencies
                    or course_dependencies
                    or course_content_dependencies
                ):
                    self.stdout.write(
                        "Not unpublishing " + website.name + " due to dependencies:"
                    )
                    if ocw_www_dependencies:
                        self.stdout.write(
                            json.dumps(
                                {
                                    "ocw_www": WebsiteContentSerializer(
                                        instance=ocw_www_dependencies, many=True
                                    ).data
                                }
                            )
                        )
                    if course_dependencies:
                        self.stdout.write(
                            json.dumps(
                                {
                                    "course": WebsiteBasicSerializer(
                                        instance=course_dependencies, many=True
                                    ).data
                                }
                            )
                        )
                    if course_content_dependencies:
                        self.stdout.write(
                            json.dumps(
                                {
                                    "course_content": WebsiteContentSerializer(
                                        instance=course_content_dependencies, many=True
                                    ).data
                                }
                            )
                        )
                else:  # unpublish
                    self.stdout.write("Unpublishing " + website.name)
                    Website.objects.filter(pk=website.pk).update(
                        unpublish_status=PUBLISH_STATUS_NOT_STARTED,
                        last_unpublished_by=user_id,
                    )
                    trigger_unpublished_removal(website)
