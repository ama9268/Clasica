from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="userprofile", name="strava_athlete_id"),
        migrations.RemoveField(model_name="userprofile", name="strava_access_token"),
        migrations.RemoveField(model_name="userprofile", name="strava_refresh_token"),
        migrations.RemoveField(model_name="userprofile", name="strava_token_expires_at"),
    ]
