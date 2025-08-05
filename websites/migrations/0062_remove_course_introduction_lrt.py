from django.db import migrations, transaction

CONTENT_TYPE_METADATA = "sitemetadata"
COURSE_INTRODUCTION_LRT = "Course Introduction"


def remove_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    with transaction.atomic():
        websites_to_update = Website.objects.filter(
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
        )
        for website in websites_to_update.iterator():
            metadata = website.metadata or {}
            metadata["learning_resource_types"].remove(COURSE_INTRODUCTION_LRT)
            website.metadata = metadata
            website.save(update_fields=["metadata"])

        contents_to_update = WebsiteContent.objects.filter(
            type=CONTENT_TYPE_METADATA,
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT,
        )
        for content in contents_to_update.iterator():
            metadata = content.metadata or {}
            metadata["learning_resource_types"].remove(COURSE_INTRODUCTION_LRT)
            content.metadata = metadata
            content.save(update_fields=["metadata"])


def restore_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    with transaction.atomic():
        websites_to_update = Website.objects.exclude(
            metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
        )
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
                content = (
                    WebsiteContent.objects.filter(
                        website_id=website.pk,
                        type=CONTENT_TYPE_METADATA,
                    )
                    .exclude(
                        metadata__learning_resource_types__contains=COURSE_INTRODUCTION_LRT
                    )
                    .first()
                )
                if content:
                    content_metadata = content.metadata or {}
                    content_lrts = content_metadata.get("learning_resource_types")
                    if isinstance(content_lrts, list):
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
