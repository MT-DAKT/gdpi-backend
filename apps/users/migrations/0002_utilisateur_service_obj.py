"""
Migration : ajoute la FK service (nullable) dans Utilisateur.
Le champ CharField 'service' est CONSERVÉ pour la compatibilité.
On peut le supprimer plus tard après migration des données.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users',    '0001_initial'),
        ('administration', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='utilisateur',
            name='service_obj',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='utilisateurs',
                to='administration.service',
                verbose_name='Service',
            ),
        ),
    ]
