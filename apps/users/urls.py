from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    UtilisateurViewSet,
)

app_name = 'users'

router = DefaultRouter()
router.register(r'', UtilisateurViewSet, basename='utilisateur')

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # ── Profil personnel ──────────────────────────────────────────────
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),

    # ── CRUD admin ────────────────────────────────────────────────────
    path('', include(router.urls)),
]
