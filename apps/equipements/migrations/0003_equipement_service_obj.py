"""
Migration : ajoute la FK service_obj (nullable) dans Equipement.
Le champ CharField 'service' est CONSERVÉ pour la compatibilité.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipements', '0002_logiciel_installationlogiciel'),
        ('administration',    '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='service_obj',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='equipements',
                to='administration.service',
                verbose_name='Service',
            ),
        ),
    ]
