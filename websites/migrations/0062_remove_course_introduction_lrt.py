from collections import defaultdict

from django.db import migrations, transaction
from django.db.models import Q

CONTENT_TYPE_METADATA = "sitemetadata"
CONTENT_TYPE_WEBSITE = "website"
COURSE_INTRODUCTION_LRT = "Course Introduction"


def remove_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    with transaction.atomic():
        websites_to_update = Website.objects.filter(
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
        )
        contents_to_update = WebsiteContent.objects.filter(
            Q(type=CONTENT_TYPE_METADATA) | Q(type=CONTENT_TYPE_WEBSITE),
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT,
        )

        remove_course_intro_from_lrt(websites_to_update)
        remove_course_intro_from_lrt(contents_to_update)


def remove_course_intro_from_lrt(items):
    for item in items.iterator():
        metadata = item.metadata or {}
        metadata["learning_resource_types"].remove(COURSE_INTRODUCTION_LRT)
        item.metadata = metadata
        item.save(update_fields=["metadata"])


def restore_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    with transaction.atomic():
        websites_to_update = Website.objects.exclude(
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
        )
        contents = (
            WebsiteContent.objects.filter(
                website_id__in=[w.pk for w in websites_to_update]
            )
            .filter(Q(type=CONTENT_TYPE_METADATA) | Q(type=CONTENT_TYPE_WEBSITE))
            .exclude(
                metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
            )
        )
        content_dict = defaultdict(list)
        for content in contents:
            content_dict[content.website_id].append(content)
        for website in websites_to_update.iterator():
            metadata = website.metadata or {}
            lrts = metadata.get("learning_resource_types")
            course_features = metadata.get("course_features")
            if (
                isinstance(lrts, list)
                and isinstance(course_features, list)
                and any(
                    f.get("feature") == COURSE_INTRODUCTION_LRT
                    for f in course_features
                    if isinstance(f, dict)
                )
            ):
                lrts.append(COURSE_INTRODUCTION_LRT)
                metadata["learning_resource_types"] = lrts
                website.metadata = metadata
                website.save(update_fields=["metadata"])

                for content in content_dict.get(website.pk, []):
                    content_metadata = content.metadata or {}
                    content_lrts = content_metadata.get("learning_resource_types")
                    if (
                        isinstance(content_lrts, list)
                        and COURSE_INTRODUCTION_LRT not in content_lrts
                    ):
                        content_lrts.append(COURSE_INTRODUCTION_LRT)
                        content_metadata["learning_resource_types"] = content_lrts
                        content.metadata = content_metadata
                        content.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0061_migrate_learning_resource_types"),
    ]

    operations = [
        migrations.RunPython(remove_course_intro_lrt, restore_course_intro_lrt),
    ]
