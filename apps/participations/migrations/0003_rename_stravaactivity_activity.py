import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("participations", "0002_remove_stravaactivity_track_geojson_and_more"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="StravaActivity",
            new_name="Activity",
        ),
        migrations.AlterModelOptions(
            name="activity",
            options={"verbose_name": "Actividad", "verbose_name_plural": "Actividades"},
        ),
        migrations.RemoveField(
            model_name="activity",
            name="strava_activity_id",
        ),
        migrations.RenameField(
            model_name="activity",
            old_name="imported_at",
            new_name="recorded_at",
        ),
        migrations.AlterField(
            model_name="activity",
            name="participation",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="activity",
                to="participations.participation",
            ),
        ),
    ]
