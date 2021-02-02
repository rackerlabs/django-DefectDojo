from django.db import migrations, models
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("dojo", "0056_index_component_name"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="system_settings",
            name="enable_hipchat_notifications",
        ),
        migrations.RemoveField(
            model_name="system_settings",
            name="hipchat_channel",
        ),
        migrations.RemoveField(
            model_name="system_settings",
            name="hipchat_site",
        ),
        migrations.RemoveField(
            model_name="system_settings",
            name="hipchat_token",
        ),
        migrations.RemoveField(
            model_name="usercontactinfo",
            name="hipchat_username",
        ),
        migrations.AddField(
            model_name="system_settings",
            name="enable_msteams_notifications",
            field=models.BooleanField(
                default=False, verbose_name="Enable Microsoft Teams notifications"
            ),
        ),
        migrations.AddField(
            model_name="system_settings",
            name="msteams_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="The full URL of the incoming webhook",
                max_length=400,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="auto_close_engagement",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="code_review",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="engagement_added",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="jira_update",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                help_text="JIRA sync happens in the background, errors will be shown as notifications/alerts so make sure to subscribe",
                max_length=24,
                verbose_name="JIRA problems",
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="other",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="jira_update",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                help_text="JIRA sync happens in the background, errors will be shown as notifications/alerts so make sure to subscribe",
                max_length=24,
                verbose_name="JIRA problems",
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="product_added",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="report_created",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="review_requested",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="scan_added",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                help_text="Triggered whenever an (re-)import has been done that created/updated/closed findings.",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="sla_breach",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                help_text="Get notified of upcoming SLA breaches",
                max_length=24,
                verbose_name="SLA breach",
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="stale_engagement",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="test_added",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="upcoming_engagement",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="notifications",
            name="user_mentioned",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("slack", "slack"),
                    ("msteams", "msteams"),
                    ("mail", "mail"),
                    ("alert", "alert"),
                ],
                default="alert",
                max_length=24,
            ),
        ),
    ]
