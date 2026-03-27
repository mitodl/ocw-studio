from django.db import migrations, models

import websites.constants as constants


class Migration(migrations.Migration):
    dependencies = [
        ("websites", "0069_update_mit_press_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="website",
            name="site_type",
            field=models.CharField(
                max_length=20,
                choices=list(zip(constants.SITE_TYPES, constants.SITE_TYPES)),
                default=constants.SITE_TYPE_OCW,
            ),
        ),
    ]
