""" Update OCW course sites and content via update_ocw_resource_data """
from mitol.common.utils.datetime import now_in_utc

from main.management.commands.filter import WebsiteFilterCommand
from ocw_import.tasks import update_ocw_resource_data


class Command(WebsiteFilterCommand):
    """Import OCW course sites and content via ocw2hugo output"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-b",
            "--bucket",
            dest="bucket",
            required=True,
            help="Bucket containing ocw2hugo output",
        )
        parser.add_argument(
            "--content-field",
            dest="content_field",
            required=False,
            help="WebsiteContent field that needs to be updated. Metadata fields can be entered as metadata.<field name>",
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
            default=10,
            type=int,
            help="Number of courses to process per celery task (default 10)",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            default=None,
            type=int,
            help="If specified, limits the overall number of course sites imported",
        )
        parser.add_argument(
            "--create-new",
            dest="create_new",
            action="store_true",
            help="Create any new content if it doesn't exist",
        )

    def handle(self, *args, **options):
        super().handle(*args, **options)
        prefix = options["prefix"]
        if prefix:
            # make sure it ends with a '/'
            prefix = prefix.rstrip("/") + "/"
        bucket_name = options["bucket"]
        limit = options["limit"]
        create_new = options["create_new"]
        content_field = options["content_field"]

        if not create_new and not content_field:
            self.stderr.write("Either --content-field or --create-new is required")

        self.stdout.write(f"Updating OCW courses from '{bucket_name}' bucket")
        start = now_in_utc()
        task = update_ocw_resource_data.delay(
            bucket_name=bucket_name,
            prefix=prefix,
            filter_list=self.filter_list,
            limit=limit,
            chunk_size=options["chunks"],
            content_field=options["content_field"],
            create_new_content=create_new,
        )
        self.stdout.write(f"Starting task {task}...")
        task.get()
        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "OCW Content Update  finished, took {} seconds".format(total_seconds)
        )
