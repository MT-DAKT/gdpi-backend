from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EquipementViewSet,
    TypeEquipementSchemaViewSet,
    LogicielViewSet,
    InstallationLogicielViewSet,
)

app_name = 'equipements'

router = DefaultRouter()
router.register(r'schemas',       TypeEquipementSchemaViewSet,  basename='schema')
router.register(r'logiciels',     LogicielViewSet,              basename='logiciel')
router.register(r'installations', InstallationLogicielViewSet,  basename='installation')
router.register(r'',              EquipementViewSet,            basename='equipement')

urlpatterns = [
    path('', include(router.urls)),
]
