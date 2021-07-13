from django.db import migrations, models
import django.db.models.deletion
import logging

logger = logging.getLogger(__name__)


def sq_clean(apps, schema_editor):
    Sonarqube_Product_model = apps.get_model('dojo', 'Sonarqube_Product')
    Tool_Configuration_model = apps.get_model('dojo', 'Tool_Configuration')
    Tool_Type_model = apps.get_model('dojo', 'Tool_Type')
    tts = Tool_Type_model.objects.filter(name='SonarQube')

    sqtc = Tool_Configuration_model.objects.filter(tool_type__in=tts).first()

    for sq in Sonarqube_Product_model.objects.filter(sonarqube_tool_config__isnull=True):
        logger.warning('Setting Product SonarQube Configuration for product {} to only existing SonarQube Tool '
                    'Configuration'.format(sq.product.pk))
        sq.sonarqube_tool_config = sqtc
        sq.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0116_test_type_active'),
    ]

    operations = [
        migrations.RunPython(sq_clean),
        migrations.AddField(
            model_name='test',
            name='sonarqube_config',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='dojo.sonarqube_product', verbose_name='SonarQube Config'),
        ),
        migrations.AlterField(
            model_name='sonarqube_product',
            name='sonarqube_tool_config',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dojo.tool_configuration',
                                    verbose_name='SonarQube Configuration'),
        ),
    ]
