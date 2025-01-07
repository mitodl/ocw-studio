# Manual migration to remove the "name" field from the metadata of existing stories


from django.db import migrations


def remove_name_from_stories_metadata(apps, schema_editor):
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    stories = WebsiteContent.objects.filter(website__name="ocw-www", type="stories")

    for story in stories:
        if story.metadata and "name" in story.metadata:
            del story.metadata["name"]
            story.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0058_websitecontent_referencing_content"),
    ]

    operations = [
        migrations.RunPython(remove_name_from_stories_metadata),
    ]
