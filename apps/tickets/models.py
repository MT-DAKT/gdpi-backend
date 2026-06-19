import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ticket_numero():
    """Génère TKT-YYYYMMDD-XXXX côté applicatif (trigger optionnel en DB)."""
    from django.db.models import Max
    today = timezone.now().strftime("%Y%m%d")
    prefix = f"TKT-{today}-"
    last = (
        Ticket.objects.filter(numero__startswith=prefix)
        .aggregate(Max("numero"))["numero__max"]
    )
    seq = int(last[-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def attachment_upload_path(instance, filename):
    return f"tickets/{instance.ticket.numero}/attachments/{filename}"


# ---------------------------------------------------------------------------
# Choix (constantes centralisées)
# ---------------------------------------------------------------------------

class Priorite(models.TextChoices):
    CRITIQUE = "critique", "Critique"
    HAUTE    = "haute",    "Haute"
    MOYENNE  = "moyenne",  "Moyenne"
    BASSE    = "basse",    "Basse"


class Statut(models.TextChoices):
    NOUVEAU       = "nouveau",       "Nouveau"
    ASSIGNE       = "assigne",       "Assigné"
    EN_COURS      = "en_cours",      "En cours"
    EN_ATTENTE    = "en_attente",    "En attente"
    RESOLU        = "resolu",        "Résolu"
    FERME         = "ferme",         "Fermé"
    ANNULE        = "annule",        "Annulé"


# Transitions autorisées : statut_actuel → [statuts suivants]
TRANSITIONS_AUTORISEES = {
    Statut.NOUVEAU:    [Statut.ASSIGNE, Statut.ANNULE],
    Statut.ASSIGNE:    [Statut.EN_COURS, Statut.EN_ATTENTE, Statut.ANNULE],
    Statut.EN_COURS:   [Statut.EN_ATTENTE, Statut.RESOLU, Statut.ANNULE],
    Statut.EN_ATTENTE: [Statut.EN_COURS, Statut.ANNULE],
    Statut.RESOLU:     [Statut.FERME, Statut.EN_COURS],  # réouverture possible
    Statut.FERME:      [],
    Statut.ANNULE:     [],
}


class TypeTicket(models.TextChoices):
    INCIDENT     = "incident",     "Incident"
    DEMANDE      = "demande",      "Demande de service"
    CHANGEMENT   = "changement",   "Changement"
    PROBLEME     = "probleme",     "Problème"


# ---------------------------------------------------------------------------
# Catégorie
# ---------------------------------------------------------------------------

class CategorieTicket(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom         = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    type_ticket = models.CharField(max_length=20, choices=TypeTicket.choices, blank=True)
    parent      = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sous_categories"
    )
    actif       = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie de ticket"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


# ---------------------------------------------------------------------------
# Configuration SLA
# ---------------------------------------------------------------------------

class ConfigSLA(models.Model):
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    priorite            = models.CharField(max_length=20, choices=Priorite.choices, unique=True)
    delai_prise_charge  = models.PositiveIntegerField(help_text="Délai de prise en charge (minutes)")
    delai_resolution    = models.PositiveIntegerField(help_text="Délai de résolution (minutes)")
    heures_ouvrables    = models.BooleanField(default=True, help_text="Calcul sur heures ouvrables uniquement")
    heure_debut         = models.TimeField(default="08:00", help_text="Début des heures ouvrables")
    heure_fin           = models.TimeField(default="18:00", help_text="Fin des heures ouvrables")
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration SLA"

    def __str__(self):
        return f"SLA {self.priorite} — prise en charge {self.delai_prise_charge}min / résolution {self.delai_resolution}min"

    def echeance_prise_charge(self, depuis: "timezone.datetime") -> "timezone.datetime":
        return depuis + timedelta(minutes=self.delai_prise_charge)

    def echeance_resolution(self, depuis: "timezone.datetime") -> "timezone.datetime":
        return depuis + timedelta(minutes=self.delai_resolution)


# ---------------------------------------------------------------------------
# Ticket (table centrale)
# ---------------------------------------------------------------------------

class Ticket(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero      = models.CharField(max_length=20, unique=True, editable=False)

    # Classification
    titre       = models.CharField(max_length=255)
    description = models.TextField()
    type_ticket = models.CharField(max_length=20, choices=TypeTicket.choices, default=TypeTicket.INCIDENT)
    categorie   = models.ForeignKey(
        CategorieTicket, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tickets"
    )
    priorite    = models.CharField(max_length=20, choices=Priorite.choices, default=Priorite.MOYENNE)
    statut      = models.CharField(max_length=20, choices=Statut.choices, default=Statut.NOUVEAU)

    # Acteurs
    demandeur   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="tickets_demandes"
    )
    assigne_a   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tickets_assignes"
    )

    # Équipement concerné (FK nullable vers module equipements)
    equipement  = models.ForeignKey(
        "equipements.Equipement", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tickets"
    )

    # SLA
    echeance_prise_charge = models.DateTimeField(null=True, blank=True)
    echeance_resolution   = models.DateTimeField(null=True, blank=True)
    pris_en_charge_le     = models.DateTimeField(null=True, blank=True)
    resolu_le             = models.DateTimeField(null=True, blank=True)
    ferme_le              = models.DateTimeField(null=True, blank=True)

    # Résolution
    solution              = models.TextField(blank=True)
    satisfaction          = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Note de satisfaction 1-5"
    )
    commentaire_cloture   = models.TextField(blank=True)

    # Escalade
    escalade              = models.BooleanField(default=False)
    escalade_le           = models.DateTimeField(null=True, blank=True)
    escalade_vers         = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tickets_escalades"
    )

    # Ticket parent (pour les sous-tickets / problèmes liés)
    parent                = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sous_tickets"
    )

    # Méta
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["priorite"]),
            models.Index(fields=["assigne_a", "statut"]),
            models.Index(fields=["demandeur"]),
            models.Index(fields=["echeance_resolution"]),
        ]

    def __str__(self):
        return f"{self.numero} — {self.titre}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = ticket_numero()
        # Calcul automatique des échéances SLA à la création
        if not self.pk:
            try:
                sla = ConfigSLA.objects.get(priorite=self.priorite)
                now = timezone.now()
                self.echeance_prise_charge = sla.echeance_prise_charge(now)
                self.echeance_resolution   = sla.echeance_resolution(now)
            except ConfigSLA.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Propriétés SLA
    # ------------------------------------------------------------------

    @property
    def sla_prise_charge_respecte(self) -> bool | None:
        if not self.echeance_prise_charge:
            return None
        ref = self.pris_en_charge_le or timezone.now()
        return ref <= self.echeance_prise_charge

    @property
    def sla_resolution_respecte(self) -> bool | None:
        if not self.echeance_resolution:
            return None
        ref = self.resolu_le or timezone.now()
        return ref <= self.echeance_resolution

    @property
    def sla_depassement_minutes(self) -> int | None:
        if not self.echeance_resolution:
            return None
        ref = self.resolu_le or timezone.now()
        delta = ref - self.echeance_resolution
        return max(0, int(delta.total_seconds() / 60))

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def peut_transitionner_vers(self, nouveau_statut: str) -> bool:
        return nouveau_statut in TRANSITIONS_AUTORISEES.get(self.statut, [])

    def transitionner(self, nouveau_statut: str, utilisateur, commentaire: str = "") -> "HistoriqueTicket":
        if not self.peut_transitionner_vers(nouveau_statut):
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f"Transition {self.statut} → {nouveau_statut} non autorisée."
            )
        ancien_statut = self.statut
        self.statut = nouveau_statut
        now = timezone.now()

        if nouveau_statut == Statut.ASSIGNE and not self.pris_en_charge_le:
            self.pris_en_charge_le = now
        elif nouveau_statut == Statut.RESOLU:
            self.resolu_le = now
        elif nouveau_statut == Statut.FERME:
            self.ferme_le = now

        self.save()
        return HistoriqueTicket.objects.create(
            ticket=self,
            auteur=utilisateur,
            champ_modifie="statut",
            ancienne_valeur=ancien_statut,
            nouvelle_valeur=nouveau_statut,
            commentaire=commentaire,
        )


# ---------------------------------------------------------------------------
# Commentaire
# ---------------------------------------------------------------------------

class Commentaire(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket     = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="commentaires")
    auteur     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    contenu    = models.TextField()
    interne    = models.BooleanField(
        default=False,
        help_text="Note interne visible uniquement par les techniciens"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.auteur} sur {self.ticket.numero}"


# ---------------------------------------------------------------------------
# Pièce jointe
# ---------------------------------------------------------------------------

class PieceJointe(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket       = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="pieces_jointes")
    commentaire  = models.ForeignKey(
        Commentaire, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pieces_jointes"
    )
    fichier      = models.FileField(upload_to=attachment_upload_path)
    nom_original = models.CharField(max_length=255)
    taille       = models.PositiveIntegerField(help_text="Taille en octets")
    mime_type    = models.CharField(max_length=100)
    uploade_par  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nom_original


# ---------------------------------------------------------------------------
# Intervention (temps passé)
# ---------------------------------------------------------------------------

class Intervention(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket       = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="interventions")
    technicien   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    description  = models.TextField()
    debut        = models.DateTimeField()
    fin          = models.DateTimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Calculé automatiquement si début + fin fournis"
    )
    sur_site     = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-debut"]

    def save(self, *args, **kwargs):
        if self.debut and self.fin and not self.duree_minutes:
            delta = self.fin - self.debut
            self.duree_minutes = max(0, int(delta.total_seconds() / 60))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Intervention {self.technicien} sur {self.ticket.numero}"


# ---------------------------------------------------------------------------
# Historique (audit trail)
# ---------------------------------------------------------------------------

class HistoriqueTicket(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket           = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="historique")
    auteur           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    champ_modifie    = models.CharField(max_length=100)
    ancienne_valeur  = models.TextField(blank=True)
    nouvelle_valeur  = models.TextField(blank=True)
    commentaire      = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.ticket.numero}] {self.champ_modifie}: {self.ancienne_valeur} → {self.nouvelle_valeur}"


# ---------------------------------------------------------------------------
# Base de connaissances
# ---------------------------------------------------------------------------

class ArticleBaseConnaissances(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre        = models.CharField(max_length=255)
    contenu      = models.TextField()
    categorie    = models.ForeignKey(
        CategorieTicket, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="articles"
    )
    ticket_source = models.ForeignKey(
        Ticket, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="articles_kb",
        help_text="Ticket à l'origine de cet article"
    )
    auteur       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    publie       = models.BooleanField(default=False)
    vues         = models.PositiveIntegerField(default=0)
    utile_oui    = models.PositiveIntegerField(default=0)
    utile_non    = models.PositiveIntegerField(default=0)
    tags         = models.JSONField(default=list, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Article base de connaissances"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publie"]),
        ]

    def __str__(self):
        return self.titre

    @property
    def score_utilite(self) -> float:
        total = self.utile_oui + self.utile_non
        return round(self.utile_oui / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class TypeNotification(models.TextChoices):
    TICKET_CREE       = "ticket_cree",       "Nouveau ticket créé"
    TICKET_ASSIGNE    = "ticket_assigne",    "Ticket assigné"
    TICKET_COMMENTE   = "ticket_commente",   "Nouveau commentaire"
    TICKET_RESOLU     = "ticket_resolu",     "Ticket résolu"
    TICKET_FERME      = "ticket_ferme",      "Ticket fermé"
    SLA_DEPASSEMENT   = "sla_depassement",   "Dépassement SLA"
    SLA_AVERTISSEMENT = "sla_avertissement", "Avertissement SLA (80%)"
    ESCALADE          = "escalade",          "Ticket escaladé"


class Notification(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinataire    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications"
    )
    ticket          = models.ForeignKey(
        Ticket, null=True, blank=True,
        on_delete=models.CASCADE, related_name="notifications"
    )
    type_notif      = models.CharField(max_length=30, choices=TypeNotification.choices)
    titre           = models.CharField(max_length=255)
    message         = models.TextField()
    lue             = models.BooleanField(default=False)
    email_envoye    = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["destinataire", "lue"]),
        ]

    def __str__(self):
        return f"[{self.type_notif}] → {self.destinataire} | {self.titre}"
