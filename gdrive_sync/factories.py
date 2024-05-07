"""gdrive_sync factory classes"""

import factory
import pytz
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from gdrive_sync import models
from gdrive_sync.constants import DRIVE_API_RESOURCES, DriveFileStatus
from websites.factories import WebsiteFactory


class DriveApiQueryTrackerFactory(DjangoModelFactory):
    """Factory for DriveApiQueryTracker"""

    api_call = FuzzyChoice(DRIVE_API_RESOURCES)
    last_page = factory.Faker("md5")
    last_dt = factory.Faker("date_time", tzinfo=pytz.utc)

    class Meta:
        model = models.DriveApiQueryTracker


class DriveFileFactory(DjangoModelFactory):
    """Factory for DriveFile"""

    file_id = factory.Faker("md5")
    name = factory.Faker("word")
    mime_type = FuzzyChoice(["video/mp4", "video/avi"])
    checksum = factory.Faker("md5")
    download_link = factory.Faker("uri")
    s3_key = factory.Faker("uri_path")
    status = FuzzyChoice(DriveFileStatus.ALL_STATUSES)
    modified_time = factory.Faker("date_time", tzinfo=pytz.utc)
    created_time = factory.Faker("date_time", tzinfo=pytz.utc)
    drive_path = factory.Faker("uri_path")
    size = factory.Faker("pyint", min_value=0, max_value=9999)
    website = factory.SubFactory(WebsiteFactory)

    class Meta:
        model = models.DriveFile
