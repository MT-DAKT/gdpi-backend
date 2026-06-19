import csv
import io
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsAdminOrRespIT, IsAdminOrRespITOrTechnicien
from .models import Equipement, TypeEquipementSchema, StatutEquipement
from .serializers import (
    EquipementDetailSerializer,
    EquipementImportSerializer,
    EquipementListSerializer,
    EquipementWriteSerializer,
    TypeEquipementSchemaSerializer,
    TypeEquipementSchemaWriteSerializer,
)


# ── VIEWSET : SCHÉMA DES TYPES ────────────────────────────────────────

class TypeEquipementSchemaViewSet(viewsets.ModelViewSet):
    """
    CRUD sur les définitions de champs par type d'équipement.
    Permet à un admin de créer un nouveau type (ex: camera_ip)
    en ajoutant ses champs sans toucher au code Python.
    """
    queryset = TypeEquipementSchema.objects.all().order_by('type_equipement', 'ordre_affichage')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type_equipement', 'actif', 'obligatoire']
    search_fields = ['type_equipement', 'champ', 'label']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TypeEquipementSchemaWriteSerializer
        return TypeEquipementSchemaSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrRespIT()]

    @action(detail=False, methods=['get'], url_path='types-disponibles')
    def types_disponibles(self, request):
        """
        Retourne la liste des types configurés, avec leurs champs.
        Utilisé par le frontend pour construire les formulaires dynamiquement.
        """
        types = (
            TypeEquipementSchema.objects
            .filter(actif=True)
            .values_list('type_equipement', flat=True)
            .distinct()
            .order_by('type_equipement')
        )
        result = {}
        for t in types:
            champs = TypeEquipementSchema.objects.filter(type_equipement=t, actif=True).order_by('ordre_affichage')
            result[t] = TypeEquipementSchemaSerializer(champs, many=True).data
        return Response(result)


# ── VIEWSET : ÉQUIPEMENTS ─────────────────────────────────────────────

class EquipementViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les équipements.
    Les attributs spécifiques au type sont dans le champ JSONB
    'attributs_specifiques' — validés dynamiquement via TypeEquipementSchema.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_equipement', 'statut', 'service']
    search_fields = ['tag_inventaire', 'nom', 'marque', 'modele', 'numero_serie', 'localisation']
    ordering_fields = ['tag_inventaire', 'nom', 'type_equipement', 'statut', 'fin_garantie', 'cree_le']

    def get_queryset(self):
        qs = Equipement.objects.select_related('utilisateur', 'technicien_referent')

        # Filtre sur attribut JSONB : ?attr_cle=ram_go&attr_val=16
        attr_cle = self.request.query_params.get('attr_cle')
        attr_val = self.request.query_params.get('attr_val')
        if attr_cle and attr_val:
            qs = qs.filter(**{f'attributs_specifiques__{attr_cle}': attr_val})

        # Filtre garantie expire dans N jours
        garantie = self.request.query_params.get('garantie_expire_dans')
        if garantie and garantie.isdigit():
            limite = timezone.now().date() + timezone.timedelta(days=int(garantie))
            qs = qs.filter(
                fin_garantie__gte=timezone.now().date(),
                fin_garantie__lte=limite,
            )
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return EquipementWriteSerializer
        if self.action == 'list':
            return EquipementListSerializer
        return EquipementDetailSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'stats', 'fin_garantie'):
            return [IsAdminOrRespITOrTechnicien()]
        return [IsAdminOrRespIT()]

    def destroy(self, request, *args, **kwargs):
        equip = self.get_object()
        equip.statut = StatutEquipement.REFORME
        equip.save(update_fields=['statut', 'modifie_le'])
        return Response(
            {'detail': f"Équipement {equip.tag_inventaire} réformé."},
            status=status.HTTP_200_OK,
        )

    # ── ACTIONS ───────────────────────────────────────────────────────

    @action(detail=True, methods=['patch'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        equip = self.get_object()
        new_statut = request.data.get('statut')
        if new_statut not in StatutEquipement.values:
            return Response(
                {'detail': f"Statut invalide. Valeurs : {', '.join(StatutEquipement.values)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        equip.statut = new_statut
        equip.save(update_fields=['statut', 'modifie_le'])
        return Response(EquipementDetailSerializer(equip).data)

    @action(detail=True, methods=['patch'], url_path='affecter')
    def affecter(self, request, pk=None):
        from apps.users.models import Utilisateur
        equip = self.get_object()
        utilisateur_id = request.data.get('utilisateur_id')

        if utilisateur_id is None:
            equip.utilisateur = None
        else:
            try:
                equip.utilisateur = Utilisateur.objects.get(id=utilisateur_id, actif=True)
            except Utilisateur.DoesNotExist:
                return Response({'detail': 'Utilisateur introuvable ou inactif.'}, status=status.HTTP_404_NOT_FOUND)

        if service := request.data.get('service'):
            equip.service = service

        equip.save(update_fields=['utilisateur', 'service', 'modifie_le'])
        return Response(EquipementDetailSerializer(equip).data)

    @action(detail=True, methods=['patch'], url_path='attributs')
    def maj_attributs(self, request, pk=None):
        """
        Mise à jour partielle des attributs JSONB uniquement.
        Merge les nouvelles valeurs avec les existantes.
        PATCH /api/v1/equipements/{id}/attributs/
        Body: {"ram_go": 32, "os": "Windows 11 Pro"}
        """
        equip = self.get_object()
        nouveaux = request.data

        if not isinstance(nouveaux, dict):
            return Response({'detail': 'Format attendu : objet JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cast via le serializer
        serializer = EquipementWriteSerializer(
            equip,
            data={'attributs_specifiques': nouveaux, 'type_equipement': equip.type_equipement},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        casted = serializer.validated_data.get('attributs_specifiques', nouveaux)

        equip.attributs_specifiques = {**equip.attributs_specifiques, **casted}
        equip.save(update_fields=['attributs_specifiques', 'modifie_le'])
        return Response(EquipementDetailSerializer(equip).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        qs = Equipement.objects.all()
        aujourd_hui = timezone.now().date()
        dans_30j = aujourd_hui + timezone.timedelta(days=30)
        dans_90j = aujourd_hui + timezone.timedelta(days=90)

        # Comptage dynamique par type (pas de liste figée)
        par_type = {}
        for row in qs.values('type_equipement').distinct():
            t = row['type_equipement']
            par_type[t] = qs.filter(type_equipement=t).count()

        return Response({
            'total': qs.count(),
            'par_statut': {s: qs.filter(statut=s).count() for s in StatutEquipement.values},
            'par_type': par_type,
            'garantie': {
                'expiree':    qs.filter(fin_garantie__lt=aujourd_hui).count(),
                'expire_30j': qs.filter(fin_garantie__gte=aujourd_hui, fin_garantie__lte=dans_30j).count(),
                'expire_90j': qs.filter(fin_garantie__gte=aujourd_hui, fin_garantie__lte=dans_90j).count(),
            },
        })

    @action(detail=False, methods=['get'], url_path='fin-garantie')
    def fin_garantie(self, request):
        jours = int(request.query_params.get('jours', 90))
        limite = timezone.now().date() + timezone.timedelta(days=jours)
        qs = self.get_queryset().filter(
            fin_garantie__gte=timezone.now().date(),
            fin_garantie__lte=limite,
        ).order_by('fin_garantie')
        return Response(EquipementListSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='import-csv', parser_classes=[MultiPartParser])
    def import_csv(self, request):
        fichier = request.FILES.get('fichier')
        if not fichier:
            return Response({'detail': 'Champ "fichier" manquant.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = fichier.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            content = fichier.read().decode('latin-1')

        reader = csv.DictReader(io.StringIO(content))
        crees, ignores, erreurs = [], [], []

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                row = {k.strip(): v.strip() for k, v in row.items() if k}
                s = EquipementImportSerializer(data=row)
                if not s.is_valid():
                    erreurs.append({'ligne': i, 'erreurs': s.errors})
                    continue

                data = s.validated_data
                tag = data['tag_inventaire']
                sn = data.get('numero_serie') or None

                if Equipement.objects.filter(
                    Q(tag_inventaire=tag) | Q(numero_serie=sn, numero_serie__isnull=False)
                ).exists():
                    ignores.append({'ligne': i, 'tag': tag, 'raison': 'Doublon'})
                    continue

                Equipement.objects.create(**data)
                crees.append(tag)

        return Response({
            'crees': len(crees),
            'ignores': len(ignores),
            'erreurs': len(erreurs),
            'detail_ignores': ignores,
            'detail_erreurs': erreurs,
        }, status=status.HTTP_200_OK if not erreurs else status.HTTP_207_MULTI_STATUS)
    
    @action(detail=True, methods=['get'], url_path='impact')
    def impact(self, request, pk=None):
        """
        GET /api/v1/equipements/{id}/impact/
 
        Analyse l'impact d'une panne de cet équipement :
        - utilisateur directement affecté
        - utilisateurs du même service
        - logiciels installés (et leur criticité)
        - tickets ouverts liés à cet équipement
        """
        from apps.tickets.models import Ticket, Statut
 
        equip = self.get_object()
 
        # ── Utilisateur directement affecté ──────────────────────────────────
        utilisateur_direct = None
        if equip.utilisateur:
            u = equip.utilisateur
            utilisateur_direct = {
                'id':    str(u.id),
                'nom':   u.nom_complet,
                'email': u.email,
                'role':  u.role,
                'raison': 'Utilisateur principal de cet équipement',
            }
 
        # ── Utilisateurs du même service ──────────────────────────────────────
        utilisateurs_service = []
 
        # Priorité : service_obj (FK) sinon fallback sur service (CharField)
        service_obj  = equip.service_obj   if hasattr(equip, 'service_obj')  else None
        service_nom  = equip.service       if equip.service                  else None
 
        if service_obj:
            from apps.users.models import Utilisateur
            qs = Utilisateur.objects.filter(
                service_obj=service_obj, actif=True
            ).exclude(
                id=equip.utilisateur_id if equip.utilisateur_id else None
            ).order_by('nom', 'prenom')
 
            utilisateurs_service = [
                {
                    'id':    str(u.id),
                    'nom':   u.nom_complet,
                    'email': u.email,
                    'role':  u.role,
                    'raison': f'Membre du service {service_obj.nom}',
                }
                for u in qs[:30]
            ]
 
        elif service_nom:
            from apps.users.models import Utilisateur
            qs = Utilisateur.objects.filter(
                service=service_nom, actif=True
            ).exclude(
                id=equip.utilisateur_id if equip.utilisateur_id else None
            ).order_by('nom', 'prenom')
 
            utilisateurs_service = [
                {
                    'id':    str(u.id),
                    'nom':   u.nom_complet,
                    'email': u.email,
                    'role':  u.role,
                    'raison': f'Membre du service {service_nom}',
                }
                for u in qs[:30]
            ]
 
        # ── Logiciels installés ───────────────────────────────────────────────
        installs = equip.logiciels_installes.select_related('logiciel').all()
        logiciels = [
            {
                'id':      str(i.logiciel.id),
                'nom':     i.logiciel.nom,
                'editeur': i.logiciel.editeur,
                'version': i.version_installee or i.logiciel.version,
                'type_licence': i.logiciel.type_licence,
                'critique': i.logiciel.type_licence in (
                    'perpetuelle', 'abonnement', 'volume'
                ),
                'nb_autres_postes': i.logiciel.installations.exclude(
                    equipement=equip
                ).count(),
            }
            for i in installs
        ]
 
        # ── Tickets ouverts liés ──────────────────────────────────────────────
        statuts_ouverts = [
            Statut.NOUVEAU, Statut.ASSIGNE,
            Statut.EN_COURS, Statut.EN_ATTENTE,
        ]
        tickets_ouverts = Ticket.objects.filter(
            equipement=equip,
            statut__in=statuts_ouverts,
        ).select_related('demandeur', 'assigne_a').order_by('-priorite', '-created_at')
 
        tickets_data = [
            {
                'id':        str(t.id),
                'numero':    t.numero,
                'titre':     t.titre,
                'priorite':  t.priorite,
                'statut':    t.statut,
                'demandeur': t.demandeur.nom_complet,
                'assigne_a': t.assigne_a.nom_complet if t.assigne_a else None,
                'sla_depasse': t.est_sla_depasse(),
                'cree_le':   t.created_at.isoformat(),
            }
            for t in tickets_ouverts[:20]
        ]
 
        # ── Niveau de risque ──────────────────────────────────────────────────
        nb_users = (1 if utilisateur_direct else 0) + len(utilisateurs_service)
        nb_logiciels_critiques = sum(1 for l in logiciels if l['critique'])
 
        score = 0
        if nb_users >= 10:           score += 3
        elif nb_users >= 5:          score += 2
        elif nb_users >= 1:          score += 1
        if nb_logiciels_critiques >= 3: score += 2
        elif nb_logiciels_critiques >= 1: score += 1
        if tickets_ouverts.count() >= 3: score += 2
        elif tickets_ouverts.count() >= 1: score += 1
        if equip.type_equipement in ('serveur', 'switch', 'routeur', 'nas'): score += 1
 
        if score >= 6:   niveau_risque = 'critique'
        elif score >= 4: niveau_risque = 'eleve'
        elif score >= 2: niveau_risque = 'modere'
        else:            niveau_risque = 'faible'
 
        return Response({
            'equipement': {
                'id':             str(equip.id),
                'tag':            equip.tag_inventaire,
                'nom':            equip.nom,
                'type':           equip.type_equipement,
                'statut':         equip.statut,
                'service':        service_obj.nom if service_obj else service_nom or '—',
                'localisation':   equip.localisation,
            },
            'resume': {
                'nb_users_total':         nb_users,
                'nb_logiciels':           len(logiciels),
                'nb_logiciels_critiques': nb_logiciels_critiques,
                'nb_tickets_ouverts':     tickets_ouverts.count(),
                'niveau_risque':          niveau_risque,
            },
            'utilisateur_direct':    utilisateur_direct,
            'utilisateurs_service':  utilisateurs_service,
            'logiciels':             logiciels,
            'tickets_ouverts':       tickets_data,
        })


# ── LOGICIELS ──────────────────────────────────────────────────────────

from .models import Logiciel, InstallationLogiciel
from .serializers import (
    LogicielListSerializer, LogicielDetailSerializer, LogicielWriteSerializer,
    InstallationLogicielSerializer, InstallationLogicielWriteSerializer,
)


class LogicielViewSet(viewsets.ModelViewSet):
    """
    CRUD Logiciels + suivi des licences.
    Actions spéciales :
      - stats           : bilan global des licences
      - expirations     : licences qui expirent bientôt
      - cle_licence     : accès sécurisé à la clé (admin only)
      - installations   : liste des installations de ce logiciel
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_licence']
    search_fields = ['nom', 'editeur', 'version']
    ordering_fields = ['nom', 'editeur', 'date_expiration', 'cree_le']

    def get_queryset(self):
        return Logiciel.objects.all().order_by('nom')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LogicielWriteSerializer
        if self.action == 'list':
            return LogicielListSerializer
        return LogicielDetailSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'stats', 'expirations', 'installations'):
            return [IsAdminOrRespITOrTechnicien()]
        return [IsAdminOrRespIT()]

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Bilan global des licences pour le tableau de bord."""
        from django.utils import timezone
        qs = Logiciel.objects.all()
        aujourd_hui = timezone.now().date()
        dans_30j = aujourd_hui + timezone.timedelta(days=30)
        dans_90j = aujourd_hui + timezone.timedelta(days=90)

        return Response({
            'total_logiciels': qs.count(),
            'par_type_licence': {
                t: qs.filter(type_licence=t).count()
                for t in ['perpetuelle', 'abonnement', 'volume', 'open_source', 'gratuit']
            },
            'licences_expirees':   qs.filter(date_expiration__lt=aujourd_hui).count(),
            'expirent_30j': qs.filter(date_expiration__gte=aujourd_hui, date_expiration__lte=dans_30j).count(),
            'expirent_90j': qs.filter(date_expiration__gte=aujourd_hui, date_expiration__lte=dans_90j).count(),
            'total_installations': InstallationLogiciel.objects.count(),
        })

    @action(detail=False, methods=['get'], url_path='expirations')
    def expirations(self, request):
        """Licences qui expirent dans N jours (défaut 90)."""
        from django.utils import timezone
        jours = int(request.query_params.get('jours', 90))
        aujourd_hui = timezone.now().date()
        limite = aujourd_hui + timezone.timedelta(days=jours)
        qs = Logiciel.objects.filter(
            date_expiration__gte=aujourd_hui,
            date_expiration__lte=limite,
        ).order_by('date_expiration')
        return Response(LogicielListSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='cle-licence', permission_classes=[IsAdminOrRespIT])
    def cle_licence(self, request, pk=None):
        """
        Retourne la clé de licence — endpoint séparé, auditable.
        Réservé aux admins et responsables IT.
        """
        logiciel = self.get_object()
        if not logiciel.cle_licence:
            return Response({'detail': 'Aucune clé enregistrée pour ce logiciel.'})
        return Response({'cle_licence': logiciel.cle_licence})

    @action(detail=True, methods=['get'], url_path='installations')
    def installations(self, request, pk=None):
        """Liste des équipements sur lesquels ce logiciel est installé."""
        logiciel = self.get_object()
        qs = logiciel.installations.select_related('equipement', 'installe_par')
        return Response(InstallationLogicielSerializer(qs, many=True).data)


# ── INSTALLATIONS LOGICIEL ─────────────────────────────────────────────

class InstallationLogicielViewSet(viewsets.ModelViewSet):
    """
    Gestion des installations (logiciel ↔ équipement).
    Chaque création vérifie le quota de licences.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['logiciel', 'equipement']
    search_fields = ['logiciel__nom', 'equipement__tag_inventaire', 'equipement__nom']
    ordering_fields = ['date_installation', 'cree_le']

    def get_queryset(self):
        return InstallationLogiciel.objects.select_related(
            'logiciel', 'equipement', 'installe_par'
        ).order_by('-date_installation')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InstallationLogicielWriteSerializer
        return InstallationLogicielSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrRespITOrTechnicien()]
        return [IsAdminOrRespIT()]

    def perform_create(self, serializer):
        serializer.save(installe_par=self.request.user)
