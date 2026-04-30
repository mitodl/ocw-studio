"""
Remove `Lecture Videos` Learning Resource Type from non-video resource
content. Since this is a data fix, there is no reverse migration implemented.
"""

from django.db import migrations

CONTENT_TYPE_RESOURCE = "resource"
RESOURCE_TYPE_VIDEO = "Video"
LECTURE_VIDEOS_LRT = "Lecture Videos"


def remove_lecture_videos_lrt_from_non_video_resources(apps, schema_editor):
    """Remove 'Lecture Videos' from learning_resource_types for non-video resources."""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    Website = apps.get_model("websites", "Website")

    resources = list(
        WebsiteContent.objects.filter(
            type=CONTENT_TYPE_RESOURCE,
            metadata__learning_resource_types__contains=LECTURE_VIDEOS_LRT,
        ).exclude(metadata__resourcetype=RESOURCE_TYPE_VIDEO)
    )

    for resource in resources:
        resource.metadata["learning_resource_types"] = [
            v for v in resource.metadata["learning_resource_types"]
            if v != LECTURE_VIDEOS_LRT
        ]

    WebsiteContent.objects.bulk_update(resources, ["metadata"])
    Website.objects.filter(
        uuid__in={r.website_id for r in resources}
    ).update(has_unpublished_live=True, has_unpublished_draft=True)


class Migration(migrations.Migration):
    """Remove Lecture Videos LRT from non-video resources."""

    dependencies = [
        ("websites", "0071_remove_buy_at_amazon_links"),
    ]

    operations = [
        migrations.RunPython(
            remove_lecture_videos_lrt_from_non_video_resources,
            migrations.RunPython.noop,
        ),
    ]
