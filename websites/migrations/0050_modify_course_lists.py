# manual migration for course lists and resource collections
from django.conf import settings
from django.db import migrations, transaction
from django.db.models import Q


def replace_field(from_field, to_field, apps):  # noqa: C901
    """Replace values from one website field for another across resource collections and course lists"""  # noqa: E501
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")
    with transaction.atomic():
        contents = []
        for course_list in WebsiteContent.objects.filter(
            website__name=settings.ROOT_WEBSITE_NAME, type="course-lists"
        ):
            if not course_list.metadata:
                continue
            for course in course_list.metadata.get("courses"):
                if not course:
                    continue
                website = Website.objects.filter(
                    Q(**{f"{from_field}": course["id"]})
                ).first()
                if website:
                    course["id"] = f"{getattr(website, to_field)}"
            course_list.save()
            contents.append(course_list)
        for resource_collection in WebsiteContent.objects.filter(
            website__name=settings.ROOT_WEBSITE_NAME, type="resource_collections"
        ):
            if not resource_collection.metadata:
                continue
            resources = resource_collection.metadata.get("resources")
            if not resources:
                continue
            contents = resources.get("content")
            if not contents:
                continue
            for content in contents:
                website = Website.objects.filter(
                    Q(**{f"{from_field}": content[-1]})
                ).first()
                if website:
                    content[-1] = f"{getattr(website, to_field)}"
            resource_collection.save()
            contents.append(resource_collection)

        for content in contents:
            content_sync_state = content.content_sync_state
            content_sync_state.synced_checksum = None
            content_sync_state.save()


def name_to_url_path(apps, schema_editor):
    """
    Replace Website.name with Website.url_path in the course lists and resource collections
    """  # noqa: E501
    replace_field("name", "url_path", apps)


def url_path_to_name(apps, schema_editor):
    """
    Replace Website.url_path with Website.name in the course lists and resource collections
    """  # noqa: E501
    replace_field("url_path", "name", apps)


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0049_website_url_path"),
    ]

    operations = [
        migrations.RunPython(name_to_url_path, url_path_to_name),
    ]
