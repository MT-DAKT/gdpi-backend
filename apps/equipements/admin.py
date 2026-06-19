from django.contrib import admin
from .models import Equipement, TypeEquipementSchema, Logiciel, InstallationLogiciel


class TypeEquipementSchemaInline(admin.TabularInline):
    model = TypeEquipementSchema
    extra = 1
    fields = ['champ', 'label', 'type_donnee', 'obligatoire', 'ordre_affichage', 'unite', 'actif']


@admin.register(TypeEquipementSchema)
class TypeEquipementSchemaAdmin(admin.ModelAdmin):
    list_display = ['type_equipement', 'champ', 'label', 'type_donnee', 'obligatoire', 'actif']
    list_filter = ['type_equipement', 'type_donnee', 'obligatoire', 'actif']
    search_fields = ['type_equipement', 'champ', 'label']
    ordering = ['type_equipement', 'ordre_affichage']


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ['tag_inventaire', 'nom', 'type_equipement', 'statut', 'localisation', 'utilisateur', 'fin_garantie']
    list_filter = ['type_equipement', 'statut', 'service']
    search_fields = ['tag_inventaire', 'nom', 'marque', 'modele', 'numero_serie']
    readonly_fields = ['id', 'cree_le', 'modifie_le']
    date_hierarchy = 'date_acquisition'
    fieldsets = (
        ('Identification', {'fields': ('id', 'tag_inventaire', 'type_equipement', 'nom', 'marque', 'modele', 'numero_serie')}),
        ('Affectation', {'fields': ('statut', 'localisation', 'service', 'utilisateur', 'technicien_referent')}),
        ('Financier', {'fields': ('date_acquisition', 'cout_achat', 'fin_garantie')}),
        ('Attributs spécifiques (JSONB)', {'fields': ('attributs_specifiques',)}),
        ('Notes', {'fields': ('notes',)}),
        ('Métadonnées', {'fields': ('cree_le', 'modifie_le'), 'classes': ('collapse',)}),
    )


class InstallationLogicielInline(admin.TabularInline):
    model = InstallationLogiciel
    extra = 0
    fields = ['logiciel', 'version_installee', 'date_installation', 'installe_par']
    autocomplete_fields = ['logiciel']


@admin.register(Logiciel)
class LogicielAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'editeur', 'version', 'type_licence', 'nb_postes_autorises', 'nb_installations', 'date_expiration', 'licence_expiree']
    list_filter   = ['type_licence', 'alerte_active']
    search_fields = ['nom', 'editeur']
    readonly_fields = ['cree_le', 'modifie_le', 'nb_installations', 'taux_utilisation_pct']
    inlines = [InstallationLogicielInline]
    fieldsets = (
        ('Identification',  {'fields': ('nom', 'editeur', 'version')}),
        ('Licence',         {'fields': ('type_licence', 'nb_postes_autorises', 'cout_annuel', 'date_achat', 'date_expiration', 'cle_licence')}),
        ('Alertes',         {'fields': ('alerte_active', 'jours_alerte')}),
        ('Utilisation',     {'fields': ('nb_installations', 'taux_utilisation_pct')}),
        ('Notes',           {'fields': ('notes',)}),
        ('Métadonnées',     {'fields': ('cree_le', 'modifie_le'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Installations')
    def nb_installations(self, obj):
        return obj.nb_installations

    @admin.display(description='Taux utilisation')
    def taux_utilisation_pct(self, obj):
        t = obj.taux_utilisation_pct
        return f'{t}%' if t is not None else '—'

    @admin.display(boolean=True, description='Expirée')
    def licence_expiree(self, obj):
        return obj.licence_expiree


@admin.register(InstallationLogiciel)
class InstallationLogicielAdmin(admin.ModelAdmin):
    list_display  = ['logiciel', 'equipement', 'version_installee', 'date_installation', 'installe_par']
    list_filter   = ['logiciel', 'date_installation']
    search_fields = ['logiciel__nom', 'equipement__tag_inventaire', 'equipement__nom']
    autocomplete_fields = ['logiciel', 'equipement']
    readonly_fields = ['cree_le']
