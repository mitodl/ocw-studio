""" Backpopulate OCW courses and content via ocw2hugo output """
from django.core.management import BaseCommand

from main.utils import now_in_utc
from websites.tasks import import_ocw2hugo_courses


class Command(BaseCommand):
    """ Backpopulate OCW courses and content via ocw2hugo output """

    help = "Backpopulate OCW courses and content via ocw2hugo output"

    def add_arguments(self, parser):
        parser.add_argument(
            "-b",
            "--bucket",
            dest="bucket",
            required=True,
            help="Bucket containing ocw2hugo output",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            dest="prefix",
            default="",
            help="S3 Bucket prefix before 'content' or 'data' folder",
        )
        parser.add_argument(
            "-c",
            "--chunks",
            dest="chunks",
            default=100,
            type=int,
            help="Number of courses to process per celery task (default 250)",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        self.stdout.write("Importing OCW courses from ocw2hugo bucket")
        prefix = options["prefix"]
        if prefix:
            # make sure it ends with a '/'
            prefix = prefix.rstrip("/") + "/"
        start = now_in_utc()
        task = import_ocw2hugo_courses.delay(
            prefix=prefix, bucket=options["bucket"], chunk_size=options["chunks"]
        )
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "OCW course import finished, took {} seconds".format(total_seconds)
        )
