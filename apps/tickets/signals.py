from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Ticket, Statut


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    if created:
        from .services import NotificationService
        NotificationService.notifier_creation(instance)
        # Si le ticket est créé directement assigné, notifier le technicien
        if instance.assigne_a:
            NotificationService.notifier_assignation(instance, instance.assigne_a)
