from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Utilisateur, RoleChoices
from .permissions import IsAdmin, IsAdminOrRespIT, IsSelfOrAdmin
from .serializers import (
    AdminSetPasswordSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    UtilisateurCreateSerializer,
    UtilisateurDetailSerializer,
    UtilisateurListSerializer,
    UtilisateurMiniSerializer,
    UtilisateurUpdateSerializer,
)


# ── AUTH ──────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    """Connexion — retourne access + refresh + infos utilisateur."""
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                user = Utilisateur.objects.get(email=request.data.get('email'))
                user.derniere_connexion = timezone.now()
                user.save(update_fields=['derniere_connexion'])
            except Utilisateur.DoesNotExist:
                pass
        return response


class LogoutView(generics.GenericAPIView):
    """Déconnexion — blackliste le refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'detail': 'Déconnexion réussie.'}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({'detail': 'Token invalide ou déjà révoqué.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveUpdateAPIView):
    """Profil de l'utilisateur connecté."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UtilisateurUpdateSerializer
        return UtilisateurDetailSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    """Changement de mot de passe par l'utilisateur lui-même."""
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Mot de passe mis à jour avec succès.'})


# ── UTILISATEURS (CRUD admin) ─────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(summary='Lister les utilisateurs'),
    retrieve=extend_schema(summary="Détail d'un utilisateur"),
    create=extend_schema(summary='Créer un utilisateur'),
    update=extend_schema(summary='Mettre à jour un utilisateur'),
    partial_update=extend_schema(summary='Mise à jour partielle'),
    destroy=extend_schema(summary='Supprimer un utilisateur'),
)
class UtilisateurViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les utilisateurs.
    - Lecture : admin + resp_it
    - Écriture : admin uniquement
    """
    queryset = Utilisateur.objects.all().order_by('nom', 'prenom')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'service', 'actif']
    search_fields = ['nom', 'prenom', 'email', 'service', 'localisation']
    ordering_fields = ['nom', 'prenom', 'email', 'cree_le', 'role']

    def get_serializer_class(self):
        if self.action == 'create':
            return UtilisateurCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UtilisateurUpdateSerializer
        if self.action == 'list':
            return UtilisateurListSerializer
        return UtilisateurDetailSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrRespIT()]
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'activer', 'desactiver', 'reset_password', 'changer_role'):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        """Désactivation douce plutôt que suppression physique."""
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'Vous ne pouvez pas désactiver votre propre compte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.actif = False
        user.save(update_fields=['actif'])
        return Response({'detail': f'Compte de {user.nom_complet} désactivé.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='activer')
    def activer(self, request, pk=None):
        """Réactiver un compte désactivé."""
        user = self.get_object()
        user.actif = True
        user.save(update_fields=['actif'])
        return Response({'detail': f'Compte de {user.nom_complet} réactivé.'})

    @action(detail=True, methods=['post'], url_path='desactiver')
    def desactiver(self, request, pk=None):
        """Désactiver un compte."""
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'Vous ne pouvez pas désactiver votre propre compte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.actif = False
        user.save(update_fields=['actif'])
        return Response({'detail': f'Compte de {user.nom_complet} désactivé.'})

    @action(detail=True, methods=['post'], url_path='reset-password',
            serializer_class=AdminSetPasswordSerializer)
    def reset_password(self, request, pk=None):
        """Réinitialisation de mot de passe par un admin."""
        user = self.get_object()
        serializer = AdminSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data['nouveau_mot_de_passe'])
        user.save(update_fields=['password'])
        return Response({'detail': f'Mot de passe de {user.nom_complet} réinitialisé.'})

    @action(detail=True, methods=['patch'], url_path='changer-role')
    def changer_role(self, request, pk=None):
        """Changer le rôle d'un utilisateur."""
        user = self.get_object()
        role = request.data.get('role')
        if role not in RoleChoices.values:
            return Response(
                {'detail': f'Rôle invalide. Valeurs acceptées : {", ".join(RoleChoices.values)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user == request.user and role != RoleChoices.ADMIN:
            return Response(
                {'detail': 'Vous ne pouvez pas retirer votre propre rôle admin.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.role = role
        user.save(update_fields=['role'])
        return Response(UtilisateurDetailSerializer(user).data)

    @action(detail=False, methods=['get'], url_path='techniciens')
    def techniciens(self, request):
        """Liste des techniciens et responsables IT — pour les menus déroulants."""
        qs = Utilisateur.objects.filter(
            role__in=[RoleChoices.TECHNICIEN, RoleChoices.RESP_IT, RoleChoices.ADMIN],
            actif=True,
        ).order_by('nom')
        return Response(UtilisateurMiniSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Statistiques rapides pour le tableau de bord."""
        qs = Utilisateur.objects.all()
        return Response({
            'total': qs.count(),
            'actifs': qs.filter(actif=True).count(),
            'inactifs': qs.filter(actif=False).count(),
            'par_role': {
                role: qs.filter(role=role).count()
                for role in RoleChoices.values
            },
        })
