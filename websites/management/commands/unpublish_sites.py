"""Unpublish course webpages provided to the command that have no dependencies. If there are dependencies, print the dependencies."""  # noqa: E501, INP001
import json

from django.conf import settings
from django.db.models import Q

from content_sync import api
from content_sync.constants import VERSION_LIVE
from content_sync.tasks import (
    remove_website_in_root_website,
    update_mass_build_pipelines_on_publish,
)
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
    """Unpublish course webpages provided to the command that have no dependencies. If there are dependencies, print the dependencies."""  # noqa: E501

    help = __doc__  # noqa: A003

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--user",
            dest="user",
            help="Email address of user that will unpublish courses",
            required=True,
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        if not self.filter_list:
            self.stderr.write("Please provide a list of course ids to unpublish.")
            return
        user_id = User.objects.filter(email__exact=options["user"]).first()
        if not user_id:
            self.stderr.write(
                "Please provide a valid email address for an existing user to unpublish courses."  # noqa: E501
            )
            return
        websites = Website.objects.filter(
            Q(name__in=self.filter_list) | Q(short_id__in=self.filter_list)
        )
        unpublished_count = 0
        unpublished_names = []
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
                unpublished_count += 1
                unpublished_names.append(website.name)
                Website.objects.filter(pk=website.pk).update(
                    unpublish_status=PUBLISH_STATUS_NOT_STARTED,
                    last_unpublished_by=user_id,
                )
                site_pipeline = api.get_site_pipeline(website)
                site_pipeline.pause_pipeline(VERSION_LIVE)
                remove_website_in_root_website(website)
                update_mass_build_pipelines_on_publish(
                    version=VERSION_LIVE, website=website
                )
        removal_pipeline = api.get_unpublished_removal_pipeline()
        removal_pipeline.unpause()
        removal_pipeline.trigger()
        self.stdout.write(str(unpublished_count) + " course sites were unpublished.")
        if unpublished_count > 0:
            self.stdout.write(
                "The following course sites were unpublished: " + str(unpublished_names)
            )
