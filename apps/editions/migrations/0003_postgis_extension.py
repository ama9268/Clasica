from django.db import migrations
from django.contrib.postgres.operations import CreateExtension

class Migration(migrations.Migration):

    dependencies = [
        ('editions', '0002_editionmedia'),
    ]

    operations = [
        CreateExtension('postgis'),
    ]
