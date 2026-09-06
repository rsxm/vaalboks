# ruff: noqa: RUF012

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ClipboardEntry",
            fields=[
                (
                    "id",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "ordering": ("created_at", "id"),
            },
        ),
    ]
