from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("dojo", "0054_dojometa_finding"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notifications",
            name="jira_update",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("hipchat", "hipchat"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                help_text="JIRA sync happens in the background, errors will be shown as notifications/alerts so make sure to subscribe",
                max_length=24,
                verbose_name="JIRA problems",
            ),
        ),
    ]
