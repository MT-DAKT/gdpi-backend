from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from .views import (
    CategorieTicketViewSet,
    ConfigSLAViewSet,
    TicketViewSet,
    CommentaireViewSet,
    PieceJointeViewSet,
    InterventionViewSet,
    HistoriqueTicketViewSet,
    ArticleKBViewSet,
    NotificationViewSet,
)

app_name = 'tickets'

# Router principal
router = DefaultRouter()
router.register(r"tickets",       TicketViewSet,           basename="ticket")
router.register(r"categories",    CategorieTicketViewSet,  basename="categorie-ticket")
router.register(r"sla",           ConfigSLAViewSet,        basename="sla")
router.register(r"kb",            ArticleKBViewSet,        basename="kb")
router.register(r"notifications", NotificationViewSet,     basename="notification")

# Nested : /tickets/{ticket_pk}/commentaires/
tickets_router = nested_routers.NestedDefaultRouter(router, r"tickets", lookup="ticket")
tickets_router.register(r"commentaires",   CommentaireViewSet,       basename="ticket-commentaire")
tickets_router.register(r"pieces-jointes", PieceJointeViewSet,       basename="ticket-pj")
tickets_router.register(r"interventions",  InterventionViewSet,      basename="ticket-intervention")
tickets_router.register(r"historique",     HistoriqueTicketViewSet,  basename="ticket-historique")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(tickets_router.urls)),
]

"""
ENDPOINTS GÉNÉRÉS :
─────────────────────────────────────────────────────────────────────
TICKETS
  GET    /api/v1/tickets/                    Liste + filtres
  POST   /api/v1/tickets/                    Créer un ticket
  GET    /api/v1/tickets/{id}/               Détail complet
  PATCH  /api/v1/tickets/{id}/               Mise à jour partielle
  DELETE /api/v1/tickets/{id}/               Suppression (admin)
  POST   /api/v1/tickets/{id}/transition/    Changer le statut
  POST   /api/v1/tickets/{id}/cloturer/      Clôturer + solution
  POST   /api/v1/tickets/{id}/escalader/     Escalader
  POST   /api/v1/tickets/{id}/assigner/      Assigner un technicien
  GET    /api/v1/tickets/stats/              Statistiques globales
  GET    /api/v1/tickets/mes-tickets/        Tickets de l'utilisateur

SOUS-RESSOURCES (nested)
  GET/POST  /api/v1/tickets/{id}/commentaires/
  POST      /api/v1/tickets/{id}/commentaires/{cid}/
  GET/POST  /api/v1/tickets/{id}/pieces-jointes/
  GET/POST  /api/v1/tickets/{id}/interventions/
  GET       /api/v1/tickets/{id}/historique/

CATÉGORIES
  CRUD  /api/v1/categories/

SLA
  CRUD  /api/v1/sla/

BASE DE CONNAISSANCES
  GET/POST  /api/v1/kb/
  GET       /api/v1/kb/{id}/
  POST      /api/v1/kb/{id}/publier/
  POST      /api/v1/kb/{id}/voter/

NOTIFICATIONS
  GET   /api/v1/notifications/
  GET   /api/v1/notifications/non-lues/
  POST  /api/v1/notifications/marquer-tout-lu/
  POST  /api/v1/notifications/{id}/marquer-lu/
─────────────────────────────────────────────────────────────────────
"""
