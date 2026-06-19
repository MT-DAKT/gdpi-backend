from django.db.models import Q
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.users.permissions import IsAdminOrRespIT, IsAdminOrRespITOrTechnicien
from .models import Service
from .serializers import (
    ServiceListSerializer, ServiceDetailSerializer, ServiceWriteSerializer,
    ServiceMiniSerializer,
)


class ServiceViewSet(viewsets.ModelViewSet):
    """
    CRUD Services + endpoint /impact/ pour analyser l'impact d'une panne.
    """
    queryset = Service.objects.all().order_by('nom')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['actif']
    search_fields    = ['nom', 'code', 'description', 'localisation']
    ordering_fields  = ['nom', 'code', 'cree_le']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ServiceWriteSerializer
        if self.action == 'list':
            return ServiceListSerializer
        return ServiceDetailSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'impact', 'utilisateurs', 'equipements'):
            return [IsAdminOrRespITOrTechnicien()]
        return [IsAdminOrRespIT()]

    # ── Action : liste des utilisateurs du service ────────────────────────────

    @action(detail=True, methods=['get'], url_path='utilisateurs')
    def utilisateurs(self, request, pk=None):
        """
        GET /api/v1/services/{id}/utilisateurs/
        Retourne les utilisateurs actifs de ce service.
        """
        service = self.get_object()
        from apps.users.serializers import UtilisateurMiniSerializer
        users = service.utilisateurs.filter(actif=True).order_by('nom', 'prenom')
        return Response(UtilisateurMiniSerializer(users, many=True).data)

    # ── Action : liste des équipements du service ─────────────────────────────

    @action(detail=True, methods=['get'], url_path='equipements')
    def equipements(self, request, pk=None):
        """
        GET /api/v1/services/{id}/equipements/
        Retourne les équipements actifs affectés à ce service.
        """
        service = self.get_object()
        from apps.equipements.serializers import EquipementListSerializer
        equips = service.equipements.filter(
            statut__in=['actif', 'maintenance']
        ).select_related('utilisateur').order_by('tag_inventaire')
        return Response(EquipementListSerializer(equips, many=True).data)

    # ── Action : analyse d'impact ─────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='impact')
    def impact(self, request, pk=None):
        """
        GET /api/v1/services/{id}/impact/
        Analyse l'impact d'une panne sur ce service :
        - utilisateurs affectés
        - équipements critiques
        - logiciels à risque
        - tickets en cours
        """
        from apps.equipements.models import Equipement, InstallationLogiciel
        from apps.tickets.models import Ticket, Statut

        service = self.get_object()

        # ── Utilisateurs du service ───────────────────────────────────────────
        users = list(
            service.utilisateurs.filter(actif=True)
            .values('id', 'nom', 'prenom', 'email', 'role')
            .order_by('nom', 'prenom')
        )
        users_data = [
            {
                'id':      str(u['id']),
                'nom':     f"{u['prenom']} {u['nom']}",
                'email':   u['email'],
                'role':    u['role'],
            }
            for u in users
        ]

        # ── Équipements du service ────────────────────────────────────────────
        equips = service.equipements.filter(
            statut__in=['actif', 'maintenance']
        ).select_related('utilisateur').prefetch_related('logiciels_installes__logiciel')

        equipements_data = []
        for eq in equips:
            installs = eq.logiciels_installes.select_related('logiciel')
            equipements_data.append({
                'id':             str(eq.id),
                'tag':            eq.tag_inventaire,
                'nom':            eq.nom,
                'type':           eq.type_equipement,
                'statut':         eq.statut,
                'utilisateur':    {
                    'id':    str(eq.utilisateur.id),
                    'nom':   eq.utilisateur.nom_complet,
                    'email': eq.utilisateur.email,
                } if eq.utilisateur else None,
                'logiciels': [
                    {
                        'id':      str(i.logiciel.id),
                        'nom':     i.logiciel.nom,
                        'editeur': i.logiciel.editeur,
                        'critique': i.logiciel.type_licence in ('perpetuelle', 'abonnement', 'volume'),
                    }
                    for i in installs
                ],
                'garantie_expiree': eq.garantie_expiree,
            })

        # ── Logiciels distincts utilisés dans le service ──────────────────────
        logiciels_ids = set()
        logiciels_data = []
        for eq_data in equipements_data:
            for log in eq_data['logiciels']:
                if log['id'] not in logiciels_ids:
                    logiciels_ids.add(log['id'])
                    logiciels_data.append(log)

        # ── Tickets ouverts liés au service ──────────────────────────────────
        tickets_ouverts = Ticket.objects.filter(
            Q(demandeur__service=service) | Q(equipement__service=service),
            statut__in=[
                Statut.NOUVEAU, Statut.ASSIGNE,
                Statut.EN_COURS, Statut.EN_ATTENTE,
            ],
        ).select_related('demandeur', 'assigne_a', 'equipement').distinct()

        tickets_data = [
            {
                'id':       str(t.id),
                'numero':   t.numero,
                'titre':    t.titre,
                'priorite': t.priorite,
                'statut':   t.statut,
                'demandeur': t.demandeur.nom_complet,
                'assigne_a': t.assigne_a.nom_complet if t.assigne_a else None,
                'equipement': t.equipement.tag_inventaire if t.equipement else None,
                'sla_depasse': t.sla_resolution_depasse,
            }
            for t in tickets_ouverts[:50]
        ]

        return Response({
            'service': {
                'id':          str(service.id),
                'nom':         service.nom,
                'code':        service.code,
                'localisation': service.localisation,
                'responsable': {
                    'nom':   service.responsable.nom_complet,
                    'email': service.responsable.email,
                } if service.responsable else None,
            },
            'resume': {
                'nb_utilisateurs':   len(users_data),
                'nb_equipements':    len(equipements_data),
                'nb_logiciels':      len(logiciels_data),
                'nb_tickets_ouverts': tickets_ouverts.count(),
                'niveau_risque':     _niveau_risque(
                    len(users_data), len(equipements_data), tickets_ouverts.count()
                ),
            },
            'utilisateurs':  users_data,
            'equipements':   equipements_data,
            'logiciels':     logiciels_data,
            'tickets_ouverts': tickets_data,
        })


def _niveau_risque(nb_users: int, nb_equips: int, nb_tickets: int) -> str:
    """Calcule un niveau de risque simple basé sur les compteurs."""
    score = 0
    if nb_users   >= 10: score += 2
    elif nb_users >= 3:  score += 1
    if nb_equips  >= 5:  score += 2
    elif nb_equips >= 2: score += 1
    if nb_tickets >= 5:  score += 2
    elif nb_tickets >= 1: score += 1

    if score >= 5: return 'critique'
    if score >= 3: return 'eleve'
    if score >= 1: return 'modere'
    return 'faible'
