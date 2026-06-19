"""
Service de notifications : in-app + email (Celery-ready).
Toute la logique métier de notification est centralisée ici.
"""
from __future__ import annotations

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import Notification, TypeNotification, Ticket, Commentaire


class NotificationService:
    """
    Crée les notifications in-app et envoie les emails.
    Chaque méthode est conçue pour être appelée directement ou
    via une tâche Celery (delay) pour l'envoi asynchrone.
    """

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    @classmethod
    def notifier_creation(cls, ticket: Ticket) -> None:
        """Notifie les admins / resp IT à la création d'un ticket."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(role__in=("admin", "resp_it"), actif=True)
        for admin in admins:
            cls._creer_notif(
                destinataire=admin,
                ticket=ticket,
                type_notif=TypeNotification.TICKET_CREE,
                titre=f"Nouveau ticket {ticket.numero}",
                message=f"{ticket.demandeur.nom_complet} a ouvert : {ticket.titre}",
            )

    @classmethod
    def notifier_assignation(cls, ticket: Ticket, technicien) -> None:
        cls._creer_notif(
            destinataire=technicien,
            ticket=ticket,
            type_notif=TypeNotification.TICKET_ASSIGNE,
            titre=f"Ticket {ticket.numero} vous a été assigné",
            message=f"Priorité : {ticket.priorite} — {ticket.titre}",
        )

    @classmethod
    def notifier_commentaire(cls, ticket: Ticket, commentaire: Commentaire) -> None:
        destinataires = set()
        if ticket.demandeur and not commentaire.interne:
            destinataires.add(ticket.demandeur)
        if ticket.assigne_a and ticket.assigne_a != commentaire.auteur:
            destinataires.add(ticket.assigne_a)
        for dest in destinataires:
            cls._creer_notif(
                destinataire=dest,
                ticket=ticket,
                type_notif=TypeNotification.TICKET_COMMENTE,
                titre=f"Nouveau commentaire sur {ticket.numero}",
                message=f"{commentaire.auteur.get_full_name()} : {commentaire.contenu[:120]}…",
            )

    @classmethod
    def notifier_transition(cls, ticket: Ticket, historique) -> None:
        destinataires = set()
        if ticket.demandeur:
            destinataires.add(ticket.demandeur)
        if ticket.assigne_a and ticket.assigne_a != historique.auteur:
            destinataires.add(ticket.assigne_a)

        type_map = {
            "resolu": TypeNotification.TICKET_RESOLU,
            "ferme":  TypeNotification.TICKET_FERME,
        }
        type_notif = type_map.get(ticket.statut, TypeNotification.TICKET_ASSIGNE)

        for dest in destinataires:
            cls._creer_notif(
                destinataire=dest,
                ticket=ticket,
                type_notif=type_notif,
                titre=f"Ticket {ticket.numero} → {ticket.statut}",
                message=historique.commentaire or f"Statut mis à jour par {historique.auteur.get_full_name()}",
            )

    @classmethod
    def notifier_resolution(cls, ticket: Ticket) -> None:
        if ticket.demandeur:
            cls._creer_notif(
                destinataire=ticket.demandeur,
                ticket=ticket,
                type_notif=TypeNotification.TICKET_RESOLU,
                titre=f"Votre ticket {ticket.numero} a été résolu",
                message=ticket.solution[:200] if ticket.solution else "Résolution enregistrée.",
            )

    @classmethod
    def notifier_escalade(cls, ticket: Ticket, cible) -> None:
        cls._creer_notif(
            destinataire=cible,
            ticket=ticket,
            type_notif=TypeNotification.ESCALADE,
            titre=f"Ticket {ticket.numero} escaladé vers vous",
            message=f"Priorité {ticket.priorite} — {ticket.titre}",
        )

    @classmethod
    def notifier_sla_avertissement(cls, ticket: Ticket) -> None:
        """Appelé par la tâche Celery de surveillance SLA."""
        if ticket.assigne_a:
            cls._creer_notif(
                destinataire=ticket.assigne_a,
                ticket=ticket,
                type_notif=TypeNotification.SLA_AVERTISSEMENT,
                titre=f"⚠️ SLA à 80% — {ticket.numero}",
                message=f"Échéance : {ticket.echeance_resolution.strftime('%d/%m/%Y %H:%M')}",
            )

    @classmethod
    def notifier_sla_depassement(cls, ticket: Ticket) -> None:
        destinataires = set()
        if ticket.assigne_a:
            destinataires.add(ticket.assigne_a)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for resp in User.objects.filter(role="resp_it", actif=True):
            destinataires.add(resp)

        for dest in destinataires:
            cls._creer_notif(
                destinataire=dest,
                ticket=ticket,
                type_notif=TypeNotification.SLA_DEPASSEMENT,
                titre=f"🔴 SLA dépassé — {ticket.numero}",
                message=f"Priorité {ticket.priorite} — {ticket.titre}",
            )

    # ------------------------------------------------------------------
    # Méthode interne
    # ------------------------------------------------------------------

    @classmethod
    def _creer_notif(cls, *, destinataire, ticket, type_notif, titre, message) -> Notification:
        notif = Notification.objects.create(
            destinataire=destinataire,
            ticket=ticket,
            type_notif=type_notif,
            titre=titre,
            message=message,
        )
        cls._envoyer_email(notif)
        return notif

    @classmethod
    def _envoyer_email(cls, notif: Notification) -> None:
        """Envoi email synchrone — remplacer par .delay() si Celery est configuré."""
        try:
            send_mail(
                subject=notif.titre,
                message=notif.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notif.destinataire.email],
                fail_silently=True,
            )
            notif.email_envoye = True
            notif.save(update_fields=["email_envoye"])
        except Exception:
            pass  # Ne jamais bloquer la transaction principale pour un email
