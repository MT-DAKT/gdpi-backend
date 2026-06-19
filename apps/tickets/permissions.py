from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrRespIT(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("admin", "resp_it")


class IsAdminOrRespITOrTechnicien(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("admin", "resp_it", "technicien")


class IsAdminOrRespITOrTechnicienOrReadOnly(BasePermission):
    """Lecture pour tous les authentifiés, écriture pour les techniciens+."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in ("admin", "resp_it", "technicien")


class IsTicketDemandeurOrTechnicien(BasePermission):
    """
    - Admin/resp_it/technicien : accès complet
    - Demandeur : peut voir et commenter son propre ticket, pas modifier les champs métier
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role in ("admin", "resp_it", "technicien"):
            return True
        if request.method in SAFE_METHODS:
            return obj.demandeur == request.user
        return False


class CanPostInternalNote(BasePermission):
    """Seuls les techniciens et admins peuvent créer des notes internes."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.data.get("interne"):
            return request.user.role in ("admin", "resp_it", "technicien")
        return True
