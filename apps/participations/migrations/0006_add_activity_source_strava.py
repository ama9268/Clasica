from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("participations", "0005_remove_track_geometry"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="source",
            field=models.CharField(
                choices=[("mobile", "App móvil"), ("strava", "Strava")],
                default="mobile",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="activity",
            name="strava_activity_id",
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
    ]
