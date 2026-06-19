from rest_framework import serializers
from .models import Service


class ServiceMiniSerializer(serializers.ModelSerializer):
    """Serializer léger pour les FK imbriquées (utilisateurs, équipements)."""
    class Meta:
        model  = Service
        fields = ['id', 'nom', 'code']


class ServiceListSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()
    nb_utilisateurs = serializers.IntegerField(read_only=True)
    nb_equipements  = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Service
        fields = [
            'id', 'nom', 'code', 'description',
            'responsable', 'responsable_nom',
            'localisation', 'actif',
            'nb_utilisateurs', 'nb_equipements',
            'cree_le',
        ]

    def get_responsable_nom(self, obj):
        return obj.responsable.nom_complet if obj.responsable else None


class ServiceDetailSerializer(serializers.ModelSerializer):
    responsable_nom    = serializers.SerializerMethodField()
    nb_utilisateurs    = serializers.IntegerField(read_only=True)
    nb_equipements     = serializers.IntegerField(read_only=True)
    nb_tickets_ouverts = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Service
        fields = [
            'id', 'nom', 'code', 'description',
            'responsable', 'responsable_nom',
            'localisation', 'actif',
            'nb_utilisateurs', 'nb_equipements', 'nb_tickets_ouverts',
            'cree_le', 'modifie_le',
        ]

    def get_responsable_nom(self, obj):
        return obj.responsable.nom_complet if obj.responsable else None


class ServiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Service
        fields = ['nom', 'code', 'description', 'responsable', 'localisation', 'actif']

    def validate_code(self, value):
        return value.upper().replace(' ', '_') if value else value
