from django.db import models
import uuid

class Service(models.Model):
    """
    Représente un service / département de l'organisation.
    Remplace le champ CharField 'service' dans Utilisateur et Equipement.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom         = models.CharField(max_length=150, unique=True, verbose_name='Nom du service')
    code        = models.CharField(
        max_length=20, unique=True, blank=True,
        verbose_name='Code court',
        help_text='Ex: DSI, DRH, DAF — généré automatiquement si vide',
    )
    description = models.TextField(blank=True, verbose_name='Description')
    responsable = models.ForeignKey(
        'users.Utilisateur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='services_geres',
        verbose_name='Responsable du service',
    )
    localisation = models.CharField(
        max_length=200, blank=True,
        verbose_name='Localisation',
        help_text='Bâtiment, étage, aile…',
    )
    actif       = models.BooleanField(default=True, verbose_name='Actif')
    cree_le     = models.DateTimeField(auto_now_add=True)
    modifie_le  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'services'
        verbose_name    = 'Service'
        verbose_name_plural = 'Services'
        ordering        = ['nom']

    def __str__(self):
        return f'{self.code} — {self.nom}' if self.code else self.nom

    def save(self, *args, **kwargs):
        # Génère un code automatique depuis le nom si vide
        if not self.code:
            self.code = self.nom[:20].upper().replace(' ', '_')
        super().save(*args, **kwargs)

    # ── Propriétés calculées ──────────────────────────────────────────────────

    @property
    def nb_utilisateurs(self):
        return self.utilisateurs.filter(actif=True).count()

    @property
    def nb_equipements(self):
        return self.equipements.filter(statut='actif').count()

    @property
    def nb_tickets_ouverts(self):
        from apps.tickets.models import Ticket
        return Ticket.objects.filter(
            demandeur__service=self,
            statut__in=['nouveau', 'assigne', 'en_cours', 'en_attente'],
        ).count()
