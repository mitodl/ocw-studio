from django.db import migrations


def set_textid_for_sitemetadata(apps, schema_editor):
    """
    At this point all text_id with type=sitemetadata should also have text_id=sitemetadata, but there was a bug where
    WebsiteContent objects were created with a different text_id. This picks the first WebsiteContent arbitrarily
    and updates it to have text_id=sitemetadata, and deletes the others.
    """  # noqa: E501
    Website = apps.get_model("websites", "Website")
    for website in Website.objects.all():
        contents = list(website.websitecontent_set.filter(type="sitemetadata"))
        if len(contents) == 0:
            continue
        for content in contents[1:]:
            # note that SafeDeleteModel isn't used in migrations so this is a regular delete  # noqa: E501
            content.delete()

        contents[0].text_id = "sitemetadata"
        contents[0].save()


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0035_website_publish"),
    ]

    operations = [
        migrations.RunPython(set_textid_for_sitemetadata, migrations.RunPython.noop)
    ]
