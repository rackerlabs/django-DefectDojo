from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dojo", "0015_findingimage_caption"),
    ]

    operations = [
        migrations.AlterField(
            model_name="finding",
            name="file_path",
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
    ]
