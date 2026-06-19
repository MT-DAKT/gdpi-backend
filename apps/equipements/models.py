import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


# ── CHOIX STATUT ───────────────────────────────────────────────────────

class StatutEquipement(models.TextChoices):
    ACTIF       = 'actif',       'Actif'
    STOCK       = 'stock',       'En stock'
    MAINTENANCE = 'maintenance', 'En maintenance'
    REFORME     = 'reforme',     'Réformé'


# ── TYPES DE DONNÉES POUR LES CHAMPS DE SCHÉMA ────────────────────────

class TypeDonnee(models.TextChoices):
    STRING  = 'string',  'Texte'
    INTEGER = 'integer', 'Entier'
    FLOAT   = 'float',   'Décimal'
    BOOLEAN = 'boolean', 'Booléen'
    IP      = 'ip',      'Adresse IP'
    MAC     = 'mac',     'Adresse MAC'
    DATE    = 'date',    'Date'


# ── TABLE : TYPE_EQUIPEMENT_SCHEMA ─────────────────────────────────────
# Définit les champs attendus pour chaque type d'équipement.
# Configurable par l'admin SANS toucher au code Python.

class TypeEquipementSchema(models.Model):
    type_equipement = models.CharField(
        max_length=50,
        verbose_name="Type d'équipement",
        help_text="Ex: pc, switch, camera_ip, nas, onduleur…",
        db_index=True,
    )
    champ = models.CharField(
        max_length=60,
        verbose_name='Nom du champ (clé JSONB)',
        help_text="Ex: ram_go, nb_ports, resolution_mp",
    )
    label = models.CharField(
        max_length=100,
        verbose_name="Label affiché",
        help_text="Ex: RAM (Go), Nombre de ports",
    )
    type_donnee = models.CharField(
        max_length=10,
        choices=TypeDonnee.choices,
        default=TypeDonnee.STRING,
        verbose_name="Type de donnée",
    )
    obligatoire = models.BooleanField(
        default=False,
        verbose_name="Obligatoire",
    )
    ordre_affichage = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
    )
    unite = models.CharField(
        max_length=20, blank=True,
        verbose_name="Unité",
        help_text="Ex: Go, MHz, W, MP",
    )
    valeur_defaut = models.CharField(
        max_length=200, blank=True,
        verbose_name="Valeur par défaut",
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        db_table = 'type_equipement_schema'
        verbose_name = "Schéma de type d'équipement"
        verbose_name_plural = "Schémas de types d'équipement"
        unique_together = [('type_equipement', 'champ')]
        ordering = ['type_equipement', 'ordre_affichage', 'champ']

    def __str__(self):
        return f"{self.type_equipement} → {self.champ} ({self.type_donnee})"


# ── TABLE PRINCIPALE : EQUIPEMENTS ────────────────────────────────────
# Champs communs en SQL strict + attributs spécifiques en JSONB.

class Equipement(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    tag_inventaire = models.CharField(
        max_length=50, unique=True,
        verbose_name='Tag inventaire',
        help_text='Ex: INF-2026-0142',
    )
    # Le type est une simple string — plus de table enfant par type.
    # L'admin peut créer "camera_ip", "nas", "onduleur" sans toucher au code.
    type_equipement = models.CharField(
        max_length=50,
        verbose_name="Type d'équipement",
        db_index=True,
    )
    nom = models.CharField(max_length=150, verbose_name='Nom / désignation')
    marque = models.CharField(max_length=100, blank=True, verbose_name='Marque')
    modele = models.CharField(max_length=150, blank=True, verbose_name='Modèle')
    numero_serie = models.CharField(
        max_length=100, blank=True, null=True, unique=True,
        verbose_name='Numéro de série',
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutEquipement.choices,
        default=StatutEquipement.ACTIF,
        verbose_name='Statut',
        db_index=True,
    )
    localisation = models.CharField(max_length=200, blank=True, verbose_name='Localisation')
    service = models.CharField(max_length=100, blank=True, verbose_name='Service', db_index=True)
    service_obj = models.ForeignKey(
        'administration.Service',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='equipements',
        verbose_name='Service',
        db_index=True,
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipements_affectes',
        verbose_name='Affecté à',
    )
    technicien_referent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipements_geres',
        verbose_name='Technicien référent',
    )

    date_acquisition = models.DateField(null=True, blank=True, verbose_name="Date d'acquisition")
    cout_achat = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Coût d'achat (FCFA)",
    )
    fin_garantie = models.DateField(null=True, blank=True, verbose_name='Fin de garantie', db_index=True)
    notes = models.TextField(blank=True, verbose_name='Notes')

    # ── JSONB — attributs spécifiques au type ──────────────────────────
    # Exemples :
    #   PC      → {"cpu": "i7-13ème", "ram_go": 16, "os": "Windows 11"}
    #   Switch  → {"nb_ports": 48, "poe": true, "firmware": "15.2"}
    #   Caméra  → {"resolution_mp": 8, "angle_vue": 110, "ir_distance_m": 30}
    attributs_specifiques = models.JSONField(
        default=dict, blank=True,
        verbose_name='Attributs spécifiques',
        help_text='Champs propres au type, définis dans TypeEquipementSchema.',
    )

    cree_le   = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    modifie_le = models.DateTimeField(auto_now=True,    verbose_name='Modifié le')

    class Meta:
        db_table = 'equipements'
        verbose_name = 'Équipement'
        verbose_name_plural = 'Équipements'
        ordering = ['tag_inventaire']
        indexes = [
            # Index GIN sur JSONB — recherches ultra-rapides sur les attributs
            models.Index(
                fields=['attributs_specifiques'],
                name='idx_equip_attrs_gin',
            ),
        ]

    def __str__(self):
        return f'[{self.tag_inventaire}] {self.nom}'

    @property
    def garantie_expiree(self):
        from django.utils import timezone
        if self.fin_garantie:
            return self.fin_garantie < timezone.now().date()
        return None

    def get_schema(self):
        """Retourne les champs définis pour ce type (depuis TypeEquipementSchema)."""
        return TypeEquipementSchema.objects.filter(
            type_equipement=self.type_equipement,
            actif=True,
        ).order_by('ordre_affichage', 'champ')

    def valider_attributs(self):
        """
        Valide attributs_specifiques contre le schéma du type.
        Lève ValidationError si un champ obligatoire est manquant.
        """
        schema = self.get_schema()
        erreurs = []

        for champ_def in schema:
            valeur = self.attributs_specifiques.get(champ_def.champ)

            # Vérif champ obligatoire
            if champ_def.obligatoire and (valeur is None or valeur == ''):
                erreurs.append(f"Champ obligatoire manquant : {champ_def.label}")
                continue

            if valeur is None:
                continue

            # Vérif type de donnée
            try:
                _caster = {
                    TypeDonnee.INTEGER: lambda v: int(v),
                    TypeDonnee.FLOAT:   lambda v: float(v),
                    TypeDonnee.BOOLEAN: lambda v: v if isinstance(v, bool) else v.lower() in ('true', '1'),
                }
                if champ_def.type_donnee in _caster:
                    _caster[champ_def.type_donnee](valeur)
            except (ValueError, AttributeError):
                erreurs.append(
                    f"Champ '{champ_def.label}' : type attendu {champ_def.type_donnee}, "
                    f"valeur reçue : {valeur!r}"
                )

        if erreurs:
            raise ValidationError({'attributs_specifiques': erreurs})


# ── LOGICIEL ───────────────────────────────────────────────────────────

class TypeLicence(models.TextChoices):
    PERPETUELLE  = 'perpetuelle',  'Perpétuelle'
    ABONNEMENT   = 'abonnement',   'Abonnement'
    VOLUME       = 'volume',       'Volume'
    OPEN_SOURCE  = 'open_source',  'Open source'
    GRATUIT      = 'gratuit',      'Gratuit'


class Logiciel(models.Model):
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom                 = models.CharField(max_length=150, verbose_name='Nom du logiciel')
    editeur             = models.CharField(max_length=150, blank=True, verbose_name='Éditeur')
    version             = models.CharField(max_length=50, blank=True, verbose_name='Version de référence')
    type_licence        = models.CharField(
        max_length=20, choices=TypeLicence.choices,
        default=TypeLicence.PERPETUELLE, verbose_name='Type de licence',
    )
    nb_postes_autorises = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Nb postes autorisés',
        help_text='Laisser vide si illimité',
    )
    cout_annuel         = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Coût annuel (FCFA)',
    )
    date_achat          = models.DateField(null=True, blank=True, verbose_name="Date d'achat")
    date_expiration     = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration",
        help_text='Laisser vide si perpétuelle',
    )
    alerte_active       = models.BooleanField(default=True, verbose_name='Alerte renouvellement')
    jours_alerte        = models.PositiveSmallIntegerField(
        default=30, verbose_name='Délai alerte (jours)',
        help_text='Alerte envoyée X jours avant expiration',
    )
    cle_licence         = models.CharField(
        max_length=255, blank=True, verbose_name='Clé de licence',
        help_text='Stockée en clair — envisager un coffre-fort pour la prod',
    )
    notes               = models.TextField(blank=True, verbose_name='Notes')
    cree_le             = models.DateTimeField(auto_now_add=True)
    modifie_le          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'logiciels'
        verbose_name = 'Logiciel'
        verbose_name_plural = 'Logiciels'
        ordering = ['nom', 'editeur']

    def __str__(self):
        return f'{self.nom} {self.version} — {self.editeur}'

    @property
    def nb_installations(self):
        return self.installations.count()

    @property
    def licence_expiree(self):
        from django.utils import timezone
        if self.date_expiration:
            return self.date_expiration < timezone.now().date()
        return False

    @property
    def alerte_expiration(self):
        """True si la licence expire dans moins de jours_alerte jours."""
        from django.utils import timezone
        if self.date_expiration and self.alerte_active:
            delta = self.date_expiration - timezone.now().date()
            return 0 <= delta.days <= self.jours_alerte
        return False

    @property
    def taux_utilisation_pct(self):
        """Pourcentage de postes utilisés par rapport aux postes autorisés."""
        if self.nb_postes_autorises:
            return round(self.nb_installations / self.nb_postes_autorises * 100, 1)
        return None


# ── INSTALLATION LOGICIEL ──────────────────────────────────────────────

class InstallationLogiciel(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    logiciel         = models.ForeignKey(
        Logiciel, on_delete=models.CASCADE,
        related_name='installations', verbose_name='Logiciel',
    )
    equipement       = models.ForeignKey(
        Equipement, on_delete=models.CASCADE,
        related_name='logiciels_installes', verbose_name='Équipement',
    )
    version_installee = models.CharField(max_length=50, blank=True, verbose_name='Version installée')
    date_installation = models.DateField(verbose_name="Date d'installation")
    installe_par      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_effectuees',
        verbose_name='Installé par',
    )
    notes             = models.TextField(blank=True, verbose_name='Notes')
    cree_le           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'installations_logiciel'
        verbose_name = 'Installation logiciel'
        verbose_name_plural = 'Installations logiciel'
        # Un logiciel ne peut être installé qu'une fois par équipement
        unique_together = [('logiciel', 'equipement')]
        ordering = ['-date_installation']

    def __str__(self):
        return f'{self.logiciel.nom} sur {self.equipement.tag_inventaire}'

    def save(self, *args, **kwargs):
        # Vérification du quota de licences avant installation
        if not self.pk:
            logiciel = self.logiciel
            if logiciel.nb_postes_autorises is not None:
                if logiciel.nb_installations >= logiciel.nb_postes_autorises:
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f"Quota de licences atteint pour '{logiciel.nom}' "
                        f"({logiciel.nb_postes_autorises} postes autorisés)."
                    )
        super().save(*args, **kwargs)
