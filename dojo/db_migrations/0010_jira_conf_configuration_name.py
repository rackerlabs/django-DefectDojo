# Generated by Django 2.2.1 on 2019-07-31 18:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0009_endpoint_remediation'),
    ]

    operations = [
        migrations.AddField(
            model_name='jira_conf',
            name='configuration_name',
            field=models.CharField(default='', help_text='Enter a name to give to this configuration', max_length=2000),
        ),
    ]
