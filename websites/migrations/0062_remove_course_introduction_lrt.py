from django.db import migrations, transaction


def remove_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    with transaction.atomic():
        for website in Website.objects.all():
            metadata = website.metadata or {}
            lrts = metadata.get("learning_resource_types")
            if isinstance(lrts, list) and "Course Introduction" in lrts:
                metadata["learning_resource_types"] = [
                    lrt for lrt in lrts if lrt != "Course Introduction"
                ]
                website.metadata = metadata
                website.save(update_fields=["metadata"])


def restore_course_intro_lrt(apps, schema_editor):
    Website = apps.get_model("websites", "Website")
    with transaction.atomic():
        for website in Website.objects.all():
            metadata = website.metadata or {}
            lrts = metadata.get("learning_resource_types")
            course_features = metadata.get("course_features")
            if (
                isinstance(lrts, list)
                and isinstance(course_features, list)
                and any(
                    f.get("feature") == "Course Introduction"
                    for f in course_features
                    if isinstance(f, dict)
                )
                and "Course Introduction" not in lrts
            ):
                lrts.append("Course Introduction")
                metadata["learning_resource_types"] = lrts
                website.metadata = metadata
                website.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0061_migrate_learning_resource_types"),
    ]

    operations = [
        migrations.RunPython(remove_course_intro_lrt, restore_course_intro_lrt),
    ]
