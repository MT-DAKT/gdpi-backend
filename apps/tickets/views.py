from django.db.models import Count, Avg, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import TicketFilter
from .models import (
    CategorieTicket, ConfigSLA, Ticket, Commentaire,
    PieceJointe, Intervention, HistoriqueTicket,
    ArticleBaseConnaissances, Notification,
    Statut, TypeNotification,
)
from .permissions import (
    IsAdminOrRespIT,
    IsAdminOrRespITOrTechnicien,
    IsAdminOrRespITOrTechnicienOrReadOnly,
    IsTicketDemandeurOrTechnicien,
    CanPostInternalNote,
)
from .serializers import (
    CategorieTicketSerializer, ConfigSLASerializer,
    TicketDetailSerializer, TicketListSerializer, TicketWriteSerializer,
    CommentaireSerializer, PieceJointeSerializer,
    InterventionSerializer, HistoriqueTicketSerializer,
    ArticleKBSerializer, NotificationSerializer,
    TransitionStatutSerializer, EscaladeSerializer, ClotureSerializer,
)
from .services import NotificationService


# ---------------------------------------------------------------------------
# Catégories
# ---------------------------------------------------------------------------

class CategorieTicketViewSet(viewsets.ModelViewSet):
    queryset = CategorieTicket.objects.filter(actif=True, parent=None).prefetch_related("sous_categories")
    serializer_class = CategorieTicketSerializer
    permission_classes = [IsAdminOrRespITOrTechnicienOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nom", "description"]


# ---------------------------------------------------------------------------
# Config SLA
# ---------------------------------------------------------------------------

class ConfigSLAViewSet(viewsets.ModelViewSet):
    queryset = ConfigSLA.objects.all().order_by("priorite")
    serializer_class = ConfigSLASerializer
    permission_classes = [IsAdminOrRespIT]


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

class TicketViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TicketFilter
    search_fields   = ["numero", "titre", "description"]
    ordering_fields = ["created_at", "updated_at", "priorite", "statut", "echeance_resolution"]
    ordering        = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Ticket.objects.select_related(
                "demandeur", "assigne_a", "categorie", "equipement", "escalade_vers"
            )
            .prefetch_related(
                "commentaires__auteur",
                "commentaires__pieces_jointes",
                "pieces_jointes",
                "interventions__technicien",
                "historique__auteur",
            )
        )
        # Un utilisateur standard ne voit que ses propres tickets
        if user.role == "utilisateur":
            qs = qs.filter(demandeur=user)
        # Un technicien voit ses tickets assignés + les non assignés
        elif user.role == "technicien":
            qs = qs.filter(Q(assigne_a=user) | Q(assigne_a=None))
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return TicketListSerializer
        if self.action in ("create", "update", "partial_update"):
            return TicketWriteSerializer
        return TicketDetailSerializer

    def get_permissions(self):
        if self.action in ("destroy",):
            return [IsAdminOrRespIT()]
        return [IsAuthenticated(), IsTicketDemandeurOrTechnicien()]

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        """Changer le statut d'un ticket (cycle de vie contrôlé)."""
        ticket = self.get_object()
        ser = TransitionStatutSerializer(
            data=request.data, context={"ticket": ticket}
        )
        ser.is_valid(raise_exception=True)

        historique = ticket.transitionner(
            ser.validated_data["nouveau_statut"],
            request.user,
            ser.validated_data.get("commentaire", ""),
        )
        NotificationService.notifier_transition(ticket, historique)
        return Response(TicketDetailSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="cloturer")
    def cloturer(self, request, pk=None):
        """Résoudre et fermer un ticket avec solution et satisfaction optionnelle."""
        ticket = self.get_object()
        ser = ClotureSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        ticket.solution           = data["solution"]
        ticket.satisfaction       = data.get("satisfaction")
        ticket.commentaire_cloture = data.get("commentaire_cloture", "")
        ticket.transitionner(Statut.RESOLU, request.user, data["solution"])

        # Création automatique d'un article KB si demandé
        if data.get("creer_article_kb"):
            ArticleBaseConnaissances.objects.create(
                titre=f"[KB] {ticket.titre}",
                contenu=data["solution"],
                categorie=ticket.categorie,
                ticket_source=ticket,
                auteur=request.user,
                publie=False,  # Passe en draft, l'admin publie manuellement
            )

        NotificationService.notifier_resolution(ticket)
        return Response(TicketDetailSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="escalader",
            permission_classes=[IsAdminOrRespITOrTechnicien])
    def escalader(self, request, pk=None):
        """Escalader le ticket vers un autre technicien / responsable."""
        ticket = self.get_object()
        ser = EscaladeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            cible = User.objects.get(id=ser.validated_data["escalade_vers"], actif=True)
        except User.DoesNotExist:
            return Response({"detail": "Utilisateur introuvable."}, status=404)

        ticket.escalade      = True
        ticket.escalade_le   = timezone.now()
        ticket.escalade_vers = cible
        ticket.assigne_a     = cible
        ticket.save()

        HistoriqueTicket.objects.create(
            ticket=ticket,
            auteur=request.user,
            champ_modifie="escalade",
            ancienne_valeur="",
            nouvelle_valeur=str(cible),
            commentaire=ser.validated_data.get("commentaire", ""),
        )
        NotificationService.notifier_escalade(ticket, cible)
        return Response(TicketDetailSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="assigner",
            permission_classes=[IsAdminOrRespITOrTechnicien])
    def assigner(self, request, pk=None):
        """Assigner / réassigner un ticket à un technicien."""
        ticket = self.get_object()
        technicien_id = request.data.get("technicien_id")
        if not technicien_id:
            return Response({"detail": "technicien_id requis."}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            tech = User.objects.get(id=technicien_id, role__in=("technicien", "resp_it", "admin"), actif=True)
        except User.DoesNotExist:
            return Response({"detail": "Technicien introuvable."}, status=404)

        ancien = ticket.assigne_a
        ticket.assigne_a = tech
        ticket.save()

        if ticket.statut == "nouveau":
            ticket.transitionner(Statut.ASSIGNE, request.user)

        HistoriqueTicket.objects.create(
            ticket=ticket, auteur=request.user,
            champ_modifie="assigne_a",
            ancienne_valeur=str(ancien) if ancien else "",
            nouvelle_valeur=str(tech),
        )
        NotificationService.notifier_assignation(ticket, tech)
        return Response(TicketDetailSerializer(ticket, context={"request": request}).data)

    # ------------------------------------------------------------------
    # Stats & tableaux de bord
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="stats", permission_classes=[IsAdminOrRespITOrTechnicien])
    def stats(self, request):
        qs = self.get_queryset()
        now = timezone.now()

        data = {
            "total": qs.count(),
            "par_statut": dict(
                qs.values_list("statut").annotate(n=Count("id")).values_list("statut", "n")
            ),
            "par_priorite": dict(
                qs.values_list("priorite").annotate(n=Count("id")).values_list("priorite", "n")
            ),
            "par_type": dict(
                qs.values_list("type_ticket").annotate(n=Count("id")).values_list("type_ticket", "n")
            ),
            "sla_depassement": qs.filter(
                echeance_resolution__lt=now,
                statut__in=["nouveau", "assigne", "en_cours", "en_attente"],
            ).count(),
            "sla_avertissement": qs.filter(
                echeance_resolution__gte=now,
                echeance_resolution__lte=now + timezone.timedelta(hours=2),
                statut__in=["nouveau", "assigne", "en_cours", "en_attente"],
            ).count(),
            "satisfaction_moyenne": qs.filter(satisfaction__isnull=False).aggregate(
                avg=Avg("satisfaction")
            )["avg"],
            "non_assignes": qs.filter(assigne_a=None, statut="nouveau").count(),
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="mes-tickets")
    def mes_tickets(self, request):
        """Tickets assignés à l'utilisateur connecté."""
        qs = self.get_queryset().filter(assigne_a=request.user)
        ser = TicketListSerializer(qs, many=True, context={"request": request})
        return Response(ser.data)


# ---------------------------------------------------------------------------
# Commentaires
# ---------------------------------------------------------------------------

class CommentaireViewSet(viewsets.ModelViewSet):
    serializer_class = CommentaireSerializer
    permission_classes = [IsAuthenticated, CanPostInternalNote]

    def get_queryset(self):
        user = self.request.user
        qs = Commentaire.objects.select_related("auteur").prefetch_related("pieces_jointes")
        if user.role not in ("admin", "resp_it", "technicien"):
            qs = qs.filter(interne=False)
        return qs.filter(ticket_id=self.kwargs["ticket_pk"])

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(pk=self.kwargs["ticket_pk"])
        commentaire = serializer.save(ticket=ticket)
        NotificationService.notifier_commentaire(ticket, commentaire)


# ---------------------------------------------------------------------------
# Pièces jointes
# ---------------------------------------------------------------------------

class PieceJointeViewSet(viewsets.ModelViewSet):
    serializer_class = PieceJointeSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return PieceJointe.objects.filter(ticket_id=self.kwargs["ticket_pk"])

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(pk=self.kwargs["ticket_pk"])
        serializer.save(ticket=ticket)


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

class InterventionViewSet(viewsets.ModelViewSet):
    serializer_class = InterventionSerializer
    permission_classes = [IsAdminOrRespITOrTechnicien]

    def get_queryset(self):
        return Intervention.objects.select_related("technicien").filter(
            ticket_id=self.kwargs["ticket_pk"]
        )

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(pk=self.kwargs["ticket_pk"])
        serializer.save(ticket=ticket)


# ---------------------------------------------------------------------------
# Historique (lecture seule)
# ---------------------------------------------------------------------------

class HistoriqueTicketViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HistoriqueTicketSerializer
    permission_classes = [IsAdminOrRespITOrTechnicien]

    def get_queryset(self):
        return HistoriqueTicket.objects.select_related("auteur").filter(
            ticket_id=self.kwargs["ticket_pk"]
        )


# ---------------------------------------------------------------------------
# Base de connaissances
# ---------------------------------------------------------------------------

class ArticleKBViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleKBSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["titre", "contenu", "tags"]

    def get_queryset(self):
        user = self.request.user
        qs = ArticleBaseConnaissances.objects.select_related("auteur", "categorie")
        if user.role in ("admin", "resp_it", "technicien"):
            return qs
        return qs.filter(publie=True)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "publier"):
            return [IsAdminOrRespITOrTechnicien()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        article = self.get_object()
        article.publie = not article.publie
        article.save()
        return Response({"publie": article.publie})

    @action(detail=True, methods=["post"])
    def voter(self, request, pk=None):
        """Voter utile/pas utile sur un article."""
        article = self.get_object()
        utile = request.data.get("utile", True)
        if utile:
            article.utile_oui += 1
        else:
            article.utile_non += 1
        article.save()
        return Response({"utile_oui": article.utile_oui, "utile_non": article.utile_non})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.vues += 1
        instance.save(update_fields=["vues"])
        return super().retrieve(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user).order_by("-created_at")

    @action(detail=False, methods=["post"], url_path="marquer-tout-lu")
    def marquer_tout_lu(self, request):
        self.get_queryset().filter(lue=False).update(lue=True)
        return Response({"detail": "Toutes les notifications marquées comme lues."})

    @action(detail=True, methods=["post"], url_path="marquer-lu")
    def marquer_lu(self, request, pk=None):
        notif = self.get_object()
        notif.lue = True
        notif.save()
        return Response({"detail": "Notification marquée comme lue."})

    @action(detail=False, methods=["get"], url_path="non-lues")
    def non_lues(self, request):
        qs = self.get_queryset().filter(lue=False)
        return Response({
            "count": qs.count(),
            "notifications": NotificationSerializer(qs[:10], many=True).data,
        })
