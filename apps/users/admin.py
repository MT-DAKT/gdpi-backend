from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    list_display = ['email', 'nom_complet', 'role', 'service', 'actif', 'cree_le']
    list_filter = ['role', 'actif', 'service']
    search_fields = ['email', 'nom', 'prenom', 'service']
    ordering = ['nom', 'prenom']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informations personnelles'), {'fields': ('nom', 'prenom', 'telephone')}),
        (_('Organisation'), {'fields': ('role', 'service', 'localisation')}),
        (_('Permissions'), {'fields': ('actif', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Dates'), {'fields': ('derniere_connexion', 'cree_le', 'modifie_le')}),
    )
    readonly_fields = ['derniere_connexion', 'cree_le', 'modifie_le']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'telephone', 'nom', 'prenom', 'role', 'service', 'password1', 'password2'),
        }),
    )
