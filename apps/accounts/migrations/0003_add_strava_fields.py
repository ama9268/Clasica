from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_remove_strava_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="strava_athlete_id",
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="strava_access_token",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="strava_refresh_token",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="strava_token_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
