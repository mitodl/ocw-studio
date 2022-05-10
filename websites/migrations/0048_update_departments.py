from functools import reduce
from itertools import product

from django.db import migrations, transaction
from django.db.models import Q


def set_cms_w_department(apps, schema_editor):
    """Update the CMS department"""
    WebsiteContent = apps.get_model("websites", "WebsiteContent")
    filter_set = ["21W", "CMS"]
    filter_query_set = [
        "website__name__istartswith",
        "website__short_id__istartswith",
    ]

    query_set = WebsiteContent.objects.filter(
        reduce(
            lambda x, y: x | y,
            [Q(**{key: value}) for key, value in product(filter_query_set, filter_set)],
        ),
    )

    query_set = query_set.filter(type="sitemetadata")
    with transaction.atomic():
        for sitemetadata in query_set.iterator():
            sitemetadata.metadata["department_numbers"] = [
                "CMS-W",
            ]
            sitemetadata.save()


class Migration(migrations.Migration):

    dependencies = [
        ("websites", "0047_unpublish_fields"),
    ]

    operations = [
        migrations.RunPython(set_cms_w_department, migrations.RunPython.noop),
    ]
