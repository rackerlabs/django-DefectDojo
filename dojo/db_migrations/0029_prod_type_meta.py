# Generated by Django 2.2.10 on 2020-02-23 07:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0028_finding_indices'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product_type',
            options={'ordering': ('name',)},
        ),
    ]
