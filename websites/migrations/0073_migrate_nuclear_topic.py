"""Migrate the Energy -> Nuclear topic to Energy -> Nuclear Energy."""

from django.db import migrations, transaction
from django.db.models import Q

CONTENT_TYPE_METADATA = "sitemetadata"
CONTENT_TYPE_WEBSITE = "website"
ENERGY_TOPIC = "Energy"
OLD_SUBTOPIC = "Nuclear"
NEW_SUBTOPIC = "Nuclear Energy"


def update_topic(topic, old_subtopic, new_subtopic):
    """Rename a single topic entry in place. Returns True if changed."""
    if isinstance(topic, list) and topic[:2] == [ENERGY_TOPIC, old_subtopic]:
        topic[1] = new_subtopic
        return True

    if isinstance(topic, dict) and topic.get("topic") == ENERGY_TOPIC:
        subtopics = topic.get("subtopics")
        if not isinstance(subtopics, list):
            return False
        changed = False
        for i, subtopic in enumerate(subtopics):
            if isinstance(subtopic, dict) and subtopic.get("subtopic") == old_subtopic:
                subtopic["subtopic"] = new_subtopic
                changed = True
            elif subtopic == old_subtopic:
                subtopics[i] = new_subtopic
                changed = True
        return changed

    return False


def update_topics(topics, old_subtopic, new_subtopic):
    """Rename subtopic values in a list of topics. Returns True if any changed."""
    if not isinstance(topics, list):
        return False
    changed = False
    for topic in topics:
        changed |= update_topic(topic, old_subtopic, new_subtopic)
    return changed


def update_items(items, old_subtopic, new_subtopic):
    """Update topic metadata on Website or WebsiteContent items."""
    website_ids = set()
    updated_items = []
    for item in items.iterator():
        metadata = item.metadata or {}
        topics = metadata.get("topics")
        if update_topics(topics, old_subtopic, new_subtopic):
            metadata["topics"] = topics
            item.metadata = metadata
            updated_items.append(item)
            website_ids.add(getattr(item, "website_id", item.pk))
    if updated_items:
        items.model.objects.bulk_update(updated_items, ["metadata"])
    return website_ids


def rename_subtopic(apps, old_subtopic, new_subtopic):
    """Rename subtopic across all Website and WebsiteContent metadata."""
    Website = apps.get_model("websites", "Website")
    WebsiteContent = apps.get_model("websites", "WebsiteContent")

    with transaction.atomic():
        website_ids = update_items(
            Website.objects.exclude(metadata=None),
            old_subtopic,
            new_subtopic,
        )
        website_ids.update(
            update_items(
                WebsiteContent.objects.filter(
                    Q(type=CONTENT_TYPE_METADATA) | Q(type=CONTENT_TYPE_WEBSITE)
                ).exclude(metadata=None),
                old_subtopic,
                new_subtopic,
            )
        )

        if website_ids:
            Website.objects.filter(pk__in=website_ids).update(
                has_unpublished_live=True,
                has_unpublished_draft=True,
            )


def migrate_nuclear_topic(apps, schema_editor):
    """Rename Energy -> Nuclear topics to Energy -> Nuclear Energy."""
    rename_subtopic(apps, OLD_SUBTOPIC, NEW_SUBTOPIC)


def reverse_nuclear_topic(apps, schema_editor):
    """Restore Energy -> Nuclear topics from Energy -> Nuclear Energy."""
    rename_subtopic(apps, NEW_SUBTOPIC, OLD_SUBTOPIC)


class Migration(migrations.Migration):
    """Migrate Nuclear topics to Nuclear Energy."""

    dependencies = [
        ("websites", "0072_remove_lecture_videos_lrt_from_non_video_resources"),
    ]

    operations = [
        migrations.RunPython(migrate_nuclear_topic, reverse_nuclear_topic),
    ]
