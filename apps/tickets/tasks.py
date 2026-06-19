"""
Tâches Celery pour la surveillance SLA.
À planifier via Celery Beat (toutes les 15 minutes recommandé).

Configuration dans settings.py :
    CELERY_BEAT_SCHEDULE = {
        'surveiller-sla': {
            'task': 'tickets.tasks.surveiller_sla',
            'schedule': crontab(minute='*/15'),
        },
    }
"""
from celery import shared_task
from django.utils import timezone


@shared_task(name="tickets.tasks.surveiller_sla")
def surveiller_sla():
    """
    Surveille les SLA toutes les 15 min :
    - Avertissement à 80% du délai écoulé
    - Dépassement si echéance dépassée
    """
    from .models import Ticket
    from .services import NotificationService

    now = timezone.now()
    statuts_ouverts = ["nouveau", "assigne", "en_cours", "en_attente"]

    # Tickets en dépassement (non encore notifiés)
    en_depassement = Ticket.objects.filter(
        echeance_resolution__lt=now,
        statut__in=statuts_ouverts,
        # On évite les doublons : pas de notif SLA_DEPASSEMENT déjà envoyée
        notifications__type_notif="sla_depassement",
    ).distinct()

    # Tickets à 80% du SLA (avertissement)
    # On calcule : now >= echeance - 20% du délai restant
    en_avertissement = Ticket.objects.filter(
        echeance_resolution__gte=now,
        echeance_resolution__lte=now + timezone.timedelta(hours=2),
        statut__in=statuts_ouverts,
    ).exclude(
        notifications__type_notif__in=["sla_avertissement", "sla_depassement"]
    ).distinct()

    for ticket in en_depassement:
        NotificationService.notifier_sla_depassement(ticket)

    for ticket in en_avertissement:
        NotificationService.notifier_sla_avertissement(ticket)

    return {
        "depassements": en_depassement.count(),
        "avertissements": en_avertissement.count(),
        "checked_at": now.isoformat(),
    }


@shared_task(name="tickets.tasks.fermer_tickets_resolus")
def fermer_tickets_resolus(jours: int = 7):
    """
    Ferme automatiquement les tickets résolus depuis plus de X jours
    sans réaction du demandeur.
    """
    from .models import Ticket, Statut
    from .models import HistoriqueTicket

    seuil = timezone.now() - timezone.timedelta(days=jours)
    tickets = Ticket.objects.filter(statut=Statut.RESOLU, resolu_le__lte=seuil)
    count = 0
    for ticket in tickets:
        ticket.statut   = Statut.FERME
        ticket.ferme_le = timezone.now()
        ticket.save()
        HistoriqueTicket.objects.create(
            ticket=ticket,
            auteur=ticket.assigne_a or ticket.demandeur,
            champ_modifie="statut",
            ancienne_valeur=Statut.RESOLU,
            nouvelle_valeur=Statut.FERME,
            commentaire=f"Fermé automatiquement après {jours} jours sans réponse.",
        )
        count += 1

    return {"fermes": count}
