from rest_framework.permissions import BasePermission
from .models import RoleChoices


class IsAdmin(BasePermission):
    """Réservé aux administrateurs."""
    message = 'Accès réservé aux administrateurs.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == RoleChoices.ADMIN
        )


class IsAdminOrRespIT(BasePermission):
    """Réservé aux admins et responsables IT."""
    message = 'Accès réservé aux administrateurs et responsables IT.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (RoleChoices.ADMIN, RoleChoices.RESP_IT)
        )


class IsAdminOrRespITOrTechnicien(BasePermission):
    """Réservé au personnel IT (admin, resp_it, technicien)."""
    message = 'Accès réservé au personnel IT.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (
                RoleChoices.ADMIN,
                RoleChoices.RESP_IT,
                RoleChoices.TECHNICIEN,
            )
        )


class IsSelfOrAdmin(BasePermission):
    """L'utilisateur peut accéder à son propre profil ; l'admin accède à tous."""
    message = "Vous ne pouvez accéder qu'à votre propre profil."

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == RoleChoices.ADMIN
            or obj == request.user
        )
