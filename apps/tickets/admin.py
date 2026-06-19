from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CategorieTicket, ConfigSLA, Ticket, Commentaire,
    PieceJointe, Intervention, HistoriqueTicket,
    ArticleBaseConnaissances, Notification,
)


@admin.register(CategorieTicket)
class CategorieTicketAdmin(admin.ModelAdmin):
    list_display = ["nom", "type_ticket", "parent", "actif"]
    list_filter  = ["type_ticket", "actif"]
    search_fields = ["nom"]


@admin.register(ConfigSLA)
class ConfigSLAAdmin(admin.ModelAdmin):
    list_display = ["priorite", "delai_prise_charge", "delai_resolution", "heures_ouvrables"]


class CommentaireInline(admin.TabularInline):
    model  = Commentaire
    extra  = 0
    fields = ["auteur", "contenu", "interne", "created_at"]
    readonly_fields = ["auteur", "created_at"]


class InterventionInline(admin.TabularInline):
    model  = Intervention
    extra  = 0
    fields = ["technicien", "description", "debut", "fin", "duree_minutes", "sur_site"]
    readonly_fields = ["duree_minutes"]


class HistoriqueInline(admin.TabularInline):
    model  = HistoriqueTicket
    extra  = 0
    readonly_fields = ["auteur", "champ_modifie", "ancienne_valeur", "nouvelle_valeur", "commentaire", "created_at"]
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display  = [
        "numero", "titre", "type_ticket", "priorite_badge",
        "statut_badge", "demandeur", "assigne_a",
        "echeance_resolution", "escalade", "created_at"
    ]
    list_filter   = ["statut", "priorite", "type_ticket", "escalade"]
    search_fields = ["numero", "titre", "demandeur__email"]
    readonly_fields = [
        "numero", "pris_en_charge_le", "resolu_le", "ferme_le",
        "echeance_prise_charge", "echeance_resolution",
        "escalade_le", "created_at", "updated_at",
    ]
    inlines = [CommentaireInline, InterventionInline, HistoriqueInline]

    PRIORITE_COLORS = {
        "critique": "#dc2626",
        "haute":    "#ea580c",
        "moyenne":  "#ca8a04",
        "basse":    "#16a34a",
    }
    STATUT_COLORS = {
        "nouveau":    "#6366f1",
        "assigne":    "#0ea5e9",
        "en_cours":   "#f59e0b",
        "en_attente": "#8b5cf6",
        "resolu":     "#10b981",
        "ferme":      "#6b7280",
        "annule":     "#ef4444",
    }

    def priorite_badge(self, obj):
        color = self.PRIORITE_COLORS.get(obj.priorite, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px">{}</span>',
            color, obj.get_priorite_display()
        )
    priorite_badge.short_description = "Priorité"

    def statut_badge(self, obj):
        color = self.STATUT_COLORS.get(obj.statut, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px">{}</span>',
            color, obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"


@admin.register(ArticleBaseConnaissances)
class ArticleKBAdmin(admin.ModelAdmin):
    list_display  = ["titre", "categorie", "auteur", "publie", "vues", "score_utilite", "created_at"]
    list_filter   = ["publie", "categorie"]
    search_fields = ["titre", "contenu"]
    readonly_fields = ["vues", "utile_oui", "utile_non", "created_at", "updated_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ["destinataire", "type_notif", "titre", "lue", "email_envoye", "created_at"]
    list_filter   = ["type_notif", "lue", "email_envoye"]
    search_fields = ["destinataire__email", "titre"]
