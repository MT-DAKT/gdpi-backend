from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.administration.models import Service
from apps.administration.serializers import ServiceMiniSerializer

from .models import Utilisateur, RoleChoices


# ── JWT ───────────────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Enrichit le payload JWT avec les infos utilisateur."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['nom_complet'] = user.nom_complet
        token['role'] = user.role
        token['actif'] = user.actif
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if not user.actif:
            raise serializers.ValidationError(
                {'detail': 'Ce compte est désactivé. Contactez un administrateur.'}
            )
        data['user'] = UtilisateurMiniSerializer(user).data
        return data


# ── UTILISATEUR ───────────────────────────────────────────────────────

class UtilisateurMiniSerializer(serializers.ModelSerializer):
    """Version allégée — utilisée dans les FK imbriquées (tickets, équipements…)."""
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom_complet', 'role', 'service']


class UtilisateurListSerializer(serializers.ModelSerializer):
    """Vue liste — pas de données sensibles."""
    nom_complet = serializers.CharField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'nom_complet',
            'role', 'role_display', 'service', 'localisation',
            'telephone', 'actif', 'cree_le',
        ]


class UtilisateurDetailSerializer(serializers.ModelSerializer):
    """Vue détail — lecture complète."""
    nom_complet = serializers.CharField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    service_obj_detail = ServiceMiniSerializer(source='service_obj', read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'nom_complet',
            'role', 'role_display', 'service', 'service_obj', 'service_obj_detail', 'localisation',
            'telephone', 'actif', 'is_staff',
            'derniere_connexion', 'cree_le', 'modifie_le',
        ]
        read_only_fields = ['id', 'derniere_connexion', 'cree_le', 'modifie_le']


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    """Création d'un compte — inclut le mot de passe."""
    password = serializers.CharField(
        write_only=True, required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True, required=True,
        style={'input_type': 'password'},
    )
    service_obj = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        required=False, allow_null=True,
    )

    class Meta:
        model = Utilisateur
        fields = [
            'email', 'nom', 'prenom', 'telephone',
            'role', 'service', 'service_obj', 'localisation',
            'password', 'password_confirm',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Les mots de passe ne correspondent pas.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UtilisateurUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour des infos — sans changement de mot de passe."""

    class Meta:
        model = Utilisateur
        fields = [
            'nom', 'prenom', 'telephone',
            'service', 'localisation',
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Changement de mot de passe par l'utilisateur connecté."""
    ancien_mot_de_passe = serializers.CharField(required=True, style={'input_type': 'password'})
    nouveau_mot_de_passe = serializers.CharField(
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    nouveau_mot_de_passe_confirm = serializers.CharField(
        required=True, style={'input_type': 'password'}
    )

    def validate_ancien_mot_de_passe(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Mot de passe actuel incorrect.')
        return value

    def validate(self, attrs):
        if attrs['nouveau_mot_de_passe'] != attrs['nouveau_mot_de_passe_confirm']:
            raise serializers.ValidationError(
                {'nouveau_mot_de_passe': 'Les nouveaux mots de passe ne correspondent pas.'}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['nouveau_mot_de_passe'])
        user.save(update_fields=['password'])
        return user


class AdminSetPasswordSerializer(serializers.Serializer):
    """Réinitialisation de mot de passe par un admin."""
    nouveau_mot_de_passe = serializers.CharField(
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
