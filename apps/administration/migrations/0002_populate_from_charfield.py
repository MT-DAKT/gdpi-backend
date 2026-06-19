"""
Migration de données : crée les objets Service depuis les valeurs
CharField existantes et les lie aux Utilisateurs + Équipements.

À lancer APRÈS 0002_utilisateur_service_obj et 0004_equipement_service_obj.
"""
from django.db import migrations


def populate_services(apps, schema_editor):
    Utilisateur = apps.get_model('users',       'Utilisateur')
    Equipement  = apps.get_model('equipements', 'Equipement')
    Service     = apps.get_model('administration',    'Service')

    # Collecter tous les noms de service distincts (non vides)
    noms = set()
    noms.update(
        Utilisateur.objects.exclude(service='').values_list('service', flat=True)
    )
    noms.update(
        Equipement.objects.exclude(service='').values_list('service', flat=True)
    )

    # Créer les objets Service manquants
    for nom in sorted(noms):
        if nom:
            Service.objects.get_or_create(
                nom=nom,
                defaults={
                    'code': nom[:20].upper().replace(' ', '_'),
                }
            )

    # Lier les utilisateurs
    for user in Utilisateur.objects.exclude(service=''):
        svc = Service.objects.filter(nom=user.service).first()
        if svc:
            Utilisateur.objects.filter(pk=user.pk).update(service_obj=svc)

    # Lier les équipements
    for eq in Equipement.objects.exclude(service=''):
        svc = Service.objects.filter(nom=eq.service).first()
        if svc:
            Equipement.objects.filter(pk=eq.pk).update(service_obj=svc)


def reverse_populate(apps, schema_editor):
    # Rien à faire en cas de rollback — les CharField sont intacts
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('administration',    '0001_initial'),
        ('users',       '0002_utilisateur_service_obj'),
        ('equipements', '0003_equipement_service_obj'),
    ]

    operations = [
        migrations.RunPython(populate_services, reverse_populate),
    ]
