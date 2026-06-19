from rest_framework import serializers
from django.utils import timezone

from .models import (
    CategorieTicket, ConfigSLA, Ticket, Commentaire,
    PieceJointe, Intervention, HistoriqueTicket,
    ArticleBaseConnaissances, Notification,
    Statut, TRANSITIONS_AUTORISEES,
)


# ---------------------------------------------------------------------------
# Catégorie
# ---------------------------------------------------------------------------

class CategorieTicketSerializer(serializers.ModelSerializer):
    sous_categories = serializers.SerializerMethodField()

    class Meta:
        model = CategorieTicket
        fields = ["id", "nom", "description", "type_ticket", "parent", "sous_categories", "actif"]

    def get_sous_categories(self, obj):
        return CategorieTicketSerializer(
            obj.sous_categories.filter(actif=True), many=True
        ).data


# ---------------------------------------------------------------------------
# Config SLA
# ---------------------------------------------------------------------------

class ConfigSLASerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigSLA
        fields = "__all__"


# ---------------------------------------------------------------------------
# Utilisateur mini (import circulaire évité)
# ---------------------------------------------------------------------------

class UtilisateurMiniSerializer(serializers.Serializer):
    """Serializer léger pour éviter l'import circulaire avec le module users."""
    id         = serializers.UUIDField()
    email      = serializers.EmailField()
    nom        = serializers.CharField(source="nom_complet")
    role       = serializers.CharField()


# ---------------------------------------------------------------------------
# Pièce jointe
# ---------------------------------------------------------------------------

class PieceJointeSerializer(serializers.ModelSerializer):
    uploade_par = UtilisateurMiniSerializer(read_only=True)

    class Meta:
        model  = PieceJointe
        fields = ["id", "nom_original", "taille", "mime_type", "fichier", "uploade_par", "created_at"]
        read_only_fields = ["id", "nom_original", "taille", "mime_type", "uploade_par", "created_at"]

    def create(self, validated_data):
        fichier = validated_data["fichier"]
        validated_data["nom_original"] = fichier.name
        validated_data["taille"]       = fichier.size
        validated_data["mime_type"]    = getattr(fichier, "content_type", "application/octet-stream")
        validated_data["uploade_par"]  = self.context["request"].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Commentaire
# ---------------------------------------------------------------------------

class CommentaireSerializer(serializers.ModelSerializer):
    auteur        = UtilisateurMiniSerializer(read_only=True)
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)

    class Meta:
        model  = Commentaire
        fields = ["id", "ticket", "auteur", "contenu", "interne", "pieces_jointes", "created_at", "updated_at"]
        read_only_fields = ["id", "auteur", "created_at", "updated_at"]

    def validate(self, data):
        request = self.context["request"]
        # Seuls les techniciens/admins peuvent poster des notes internes
        if data.get("interne") and not hasattr(request.user, "role"):
            raise serializers.ValidationError("Vous n'avez pas le droit de poster une note interne.")
        return data

    def create(self, validated_data):
        validated_data["auteur"] = self.context["request"].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Intervention
# ---------------------------------------------------------------------------

class InterventionSerializer(serializers.ModelSerializer):
    technicien = UtilisateurMiniSerializer(read_only=True)

    class Meta:
        model  = Intervention
        fields = [
            "id", "ticket", "technicien", "description",
            "debut", "fin", "duree_minutes", "sur_site", "created_at"
        ]
        read_only_fields = ["id", "technicien", "duree_minutes", "created_at"]

    def validate(self, data):
        if data.get("fin") and data.get("debut") and data["fin"] <= data["debut"]:
            raise serializers.ValidationError("La date de fin doit être après le début.")
        return data

    def create(self, validated_data):
        validated_data["technicien"] = self.context["request"].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Historique
# ---------------------------------------------------------------------------

class HistoriqueTicketSerializer(serializers.ModelSerializer):
    auteur = UtilisateurMiniSerializer(read_only=True)

    class Meta:
        model  = HistoriqueTicket
        fields = ["id", "auteur", "champ_modifie", "ancienne_valeur", "nouvelle_valeur", "commentaire", "created_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Ticket — lecture (détail complet)
# ---------------------------------------------------------------------------

class TicketDetailSerializer(serializers.ModelSerializer):
    demandeur      = UtilisateurMiniSerializer(read_only=True)
    assigne_a      = UtilisateurMiniSerializer(read_only=True)
    escalade_vers  = UtilisateurMiniSerializer(read_only=True)
    categorie      = CategorieTicketSerializer(read_only=True)
    commentaires   = CommentaireSerializer(many=True, read_only=True)
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)
    interventions  = InterventionSerializer(many=True, read_only=True)
    historique     = HistoriqueTicketSerializer(many=True, read_only=True)

    sla_prise_charge_respecte = serializers.BooleanField(read_only=True)
    sla_resolution_respecte   = serializers.BooleanField(read_only=True)
    sla_depassement_minutes   = serializers.IntegerField(read_only=True)
    transitions_disponibles   = serializers.SerializerMethodField()

    # Infos équipement (nom + tag uniquement, évite import circulaire)
    equipement_info = serializers.SerializerMethodField()

    class Meta:
        model  = Ticket
        fields = [
            "id", "numero", "titre", "description", "type_ticket", "categorie",
            "priorite", "statut", "demandeur", "assigne_a",
            "equipement", "equipement_info",
            "echeance_prise_charge", "echeance_resolution",
            "pris_en_charge_le", "resolu_le", "ferme_le",
            "solution", "satisfaction", "commentaire_cloture",
            "escalade", "escalade_le", "escalade_vers",
            "parent",
            "sla_prise_charge_respecte", "sla_resolution_respecte", "sla_depassement_minutes",
            "transitions_disponibles",
            "commentaires", "pieces_jointes", "interventions", "historique",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "numero", "pris_en_charge_le", "resolu_le", "ferme_le",
            "echeance_prise_charge", "echeance_resolution",
            "escalade_le", "created_at", "updated_at",
        ]

    def get_transitions_disponibles(self, obj):
        return TRANSITIONS_AUTORISEES.get(obj.statut, [])

    def get_equipement_info(self, obj):
        if not obj.equipement:
            return None
        return {
            "id":   str(obj.equipement.id),
            "nom":  obj.equipement.nom,
            "tag":  obj.equipement.tag_inventaire,
            "type": obj.equipement.type_equipement,
        }


# ---------------------------------------------------------------------------
# Ticket — liste (allégé)
# ---------------------------------------------------------------------------

class TicketListSerializer(serializers.ModelSerializer):
    demandeur_nom = serializers.CharField(source="demandeur.get_full_name", read_only=True)
    assigne_nom   = serializers.CharField(source="assigne_a.get_full_name", read_only=True, default=None)
    sla_ok        = serializers.BooleanField(source="sla_resolution_respecte", read_only=True)

    class Meta:
        model  = Ticket
        fields = [
            "id", "numero", "titre", "type_ticket", "priorite", "statut",
            "demandeur_nom", "assigne_nom",
            "echeance_resolution", "sla_ok",
            "created_at", "updated_at",
        ]


# ---------------------------------------------------------------------------
# Ticket — création / mise à jour
# ---------------------------------------------------------------------------

class TicketWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Ticket
        fields = [
            "titre", "description", "type_ticket", "categorie",
            "priorite", "assigne_a", "equipement", "parent",
        ]

    def create(self, validated_data):
        validated_data["demandeur"] = self.context["request"].user
        ticket = super().create(validated_data)
        # Historique de création
        HistoriqueTicket.objects.create(
            ticket=ticket,
            auteur=ticket.demandeur,
            champ_modifie="création",
            ancienne_valeur="",
            nouvelle_valeur=ticket.statut,
        )
        return ticket

    def update(self, instance, validated_data):
        champs_surveilles = ["priorite", "assigne_a", "categorie", "equipement"]
        historiques = []
        for champ in champs_surveilles:
            if champ in validated_data:
                ancienne = str(getattr(instance, champ) or "")
                nouvelle = str(validated_data[champ] or "")
                if ancienne != nouvelle:
                    historiques.append(HistoriqueTicket(
                        ticket=instance,
                        auteur=self.context["request"].user,
                        champ_modifie=champ,
                        ancienne_valeur=ancienne,
                        nouvelle_valeur=nouvelle,
                    ))
        ticket = super().update(instance, validated_data)
        HistoriqueTicket.objects.bulk_create(historiques)
        return ticket


# ---------------------------------------------------------------------------
# Transition de statut
# ---------------------------------------------------------------------------

class TransitionStatutSerializer(serializers.Serializer):
    nouveau_statut = serializers.ChoiceField(choices=Statut.choices)
    commentaire    = serializers.CharField(required=False, allow_blank=True)

    def validate_nouveau_statut(self, value):
        ticket = self.context["ticket"]
        if not ticket.peut_transitionner_vers(value):
            raise serializers.ValidationError(
                f"Transition '{ticket.statut}' → '{value}' non autorisée. "
                f"Transitions possibles : {TRANSITIONS_AUTORISEES.get(ticket.statut, [])}"
            )
        return value


# ---------------------------------------------------------------------------
# Escalade
# ---------------------------------------------------------------------------

class EscaladeSerializer(serializers.Serializer):
    escalade_vers = serializers.UUIDField()
    commentaire   = serializers.CharField(required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# Clôture avec satisfaction
# ---------------------------------------------------------------------------

class ClotureSerializer(serializers.Serializer):
    solution             = serializers.CharField()
    satisfaction         = serializers.IntegerField(min_value=1, max_value=5, required=False)
    commentaire_cloture  = serializers.CharField(required=False, allow_blank=True)
    creer_article_kb     = serializers.BooleanField(default=False)


# ---------------------------------------------------------------------------
# Base de connaissances
# ---------------------------------------------------------------------------

class ArticleKBSerializer(serializers.ModelSerializer):
    auteur       = UtilisateurMiniSerializer(read_only=True)
    score_utilite = serializers.FloatField(read_only=True)

    class Meta:
        model  = ArticleBaseConnaissances
        fields = [
            "id", "titre", "contenu", "categorie", "ticket_source",
            "auteur", "publie", "vues", "utile_oui", "utile_non",
            "score_utilite", "tags", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "auteur", "vues", "utile_oui", "utile_non", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["auteur"] = self.context["request"].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = ["id", "ticket", "type_notif", "titre", "message", "lue", "created_at"]
        read_only_fields = fields
