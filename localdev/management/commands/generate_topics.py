""" Import OCW course sites and content via ocw2hugo output """
import os

import yaml
from django.conf import settings
from django.core.management import BaseCommand

from ocw_import.api import fetch_ocw2hugo_course_paths, generate_topics_dict


class Command(BaseCommand):
    """Generate yaml for topics and write it to """

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "-b",
            "--bucket",
            dest="bucket",
            help="The bucket with the parsed JSON files",
        )

    def handle(self, *args, **options):
        bucket_name = options["bucket"]
        self.stdout.write("Generating list of parsed JSON file paths...")
        course_paths = list(fetch_ocw2hugo_course_paths(bucket_name))
        self.stdout.write(f"Compiling topics for {len(course_paths)} paths...")
        topics = generate_topics_dict(course_paths, bucket_name)

        topics_output_path = "topics.yml"
        self.stdout.write(f"Writing out topics to {topics_output_path}...")
        with open(os.path.join(settings.BASE_DIR, topics_output_path), "w") as f:
            yaml.dump(topics, f)
