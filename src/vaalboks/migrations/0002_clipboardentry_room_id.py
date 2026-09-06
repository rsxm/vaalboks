from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("vaalboks", "0001_initial"),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name="clipboardentry",
            name="room_id",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
    ]
