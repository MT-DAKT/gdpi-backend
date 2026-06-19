from rest_framework import serializers
from apps.administration.serializers import ServiceMiniSerializer
from apps.users.serializers import UtilisateurMiniSerializer
from .models import Equipement, TypeEquipementSchema, StatutEquipement, TypeDonnee


class TypeEquipementSchemaSerializer(serializers.ModelSerializer):
    type_donnee_display = serializers.CharField(source='get_type_donnee_display', read_only=True)

    class Meta:
        model = TypeEquipementSchema
        fields = [
            'id', 'type_equipement', 'champ', 'label',
            'type_donnee', 'type_donnee_display',
            'obligatoire', 'ordre_affichage', 'unite',
            'valeur_defaut', 'actif',
        ]


class TypeEquipementSchemaWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeEquipementSchema
        fields = [
            'type_equipement', 'champ', 'label',
            'type_donnee', 'obligatoire', 'ordre_affichage',
            'unite', 'valeur_defaut', 'actif',
        ]


class EquipementListSerializer(serializers.ModelSerializer):
    utilisateur = UtilisateurMiniSerializer(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    garantie_expiree = serializers.BooleanField(read_only=True)

    class Meta:
        model = Equipement
        fields = [
            'id', 'tag_inventaire', 'nom', 'marque', 'modele',
            'type_equipement', 'statut', 'statut_display',
            'localisation', 'service',
            'utilisateur', 'fin_garantie', 'garantie_expiree',
            'cree_le',
        ]


class EquipementDetailSerializer(serializers.ModelSerializer):
    utilisateur = UtilisateurMiniSerializer(read_only=True)
    technicien_referent = UtilisateurMiniSerializer(read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    service_obj_detail = ServiceMiniSerializer(source='service_obj', read_only=True)
    garantie_expiree = serializers.BooleanField(read_only=True)
    schema_type = serializers.SerializerMethodField()

    class Meta:
        model = Equipement
        fields = [
            'id', 'tag_inventaire', 'nom', 'marque', 'modele', 'numero_serie',
            'type_equipement', 'statut', 'statut_display',
            'localisation', 'service', 'service_obj_detail',
            'utilisateur', 'technicien_referent',
            'date_acquisition', 'cout_achat', 'fin_garantie', 'garantie_expiree',
            'notes', 'attributs_specifiques', 'schema_type',
            'cree_le', 'modifie_le',
        ]

    def get_schema_type(self, obj):
        schema = TypeEquipementSchema.objects.filter(
            type_equipement=obj.type_equipement, actif=True
        ).order_by('ordre_affichage', 'champ')
        return TypeEquipementSchemaSerializer(schema, many=True).data


class EquipementWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Equipement
        fields = [
            'tag_inventaire', 'type_equipement', 'nom', 'marque', 'modele',
            'numero_serie', 'statut', 'localisation', 'service', 'service_obj',
            'utilisateur', 'technicien_referent',
            'date_acquisition', 'cout_achat', 'fin_garantie', 'notes',
            'attributs_specifiques',
        ]

    def _cast_attributs(self, type_equipement, attributs):
        schema = {
            s.champ: s
            for s in TypeEquipementSchema.objects.filter(
                type_equipement=type_equipement, actif=True
            )
        }
        casted, erreurs = {}, {}
        for cle, valeur in attributs.items():
            if cle not in schema:
                casted[cle] = valeur
                continue
            champ_def = schema[cle]
            try:
                if champ_def.type_donnee == TypeDonnee.INTEGER:
                    casted[cle] = int(valeur)
                elif champ_def.type_donnee == TypeDonnee.FLOAT:
                    casted[cle] = float(valeur)
                elif champ_def.type_donnee == TypeDonnee.BOOLEAN:
                    casted[cle] = valeur if isinstance(valeur, bool) else str(valeur).lower() in ('true', '1', 'oui')
                else:
                    casted[cle] = valeur
            except (ValueError, TypeError):
                erreurs[cle] = f"Type attendu : {champ_def.type_donnee}, valeur : {valeur!r}"
        return casted, erreurs

    def validate(self, attrs):
        type_eq = attrs.get('type_equipement') or (
            self.instance.type_equipement if self.instance else None
        )
        attributs = attrs.get('attributs_specifiques', {})

        if type_eq and attributs:
            casted, erreurs = self._cast_attributs(type_eq, attributs)
            if erreurs:
                raise serializers.ValidationError({'attributs_specifiques': erreurs})
            attrs['attributs_specifiques'] = casted

        if type_eq:
            champs_obligatoires = list(
                TypeEquipementSchema.objects.filter(
                    type_equipement=type_eq, obligatoire=True, actif=True
                ).values_list('champ', flat=True)
            )
            manquants = [c for c in champs_obligatoires if not attributs.get(c)]
            if manquants:
                raise serializers.ValidationError({
                    'attributs_specifiques': f"Champs obligatoires manquants pour '{type_eq}': {', '.join(manquants)}"
                })
        return attrs

    def update(self, instance, validated_data):
        new_attrs = validated_data.pop('attributs_specifiques', None)
        if new_attrs is not None:
            validated_data['attributs_specifiques'] = {**instance.attributs_specifiques, **new_attrs}
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EquipementImportSerializer(serializers.Serializer):
    tag_inventaire   = serializers.CharField(max_length=50)
    type_equipement  = serializers.CharField(max_length=50)
    nom              = serializers.CharField(max_length=150)
    marque           = serializers.CharField(max_length=100, required=False, allow_blank=True)
    modele           = serializers.CharField(max_length=150, required=False, allow_blank=True)
    numero_serie     = serializers.CharField(max_length=100, required=False, allow_blank=True)
    statut           = serializers.ChoiceField(choices=StatutEquipement.values, default=StatutEquipement.ACTIF)
    localisation     = serializers.CharField(max_length=200, required=False, allow_blank=True)
    service          = serializers.CharField(max_length=100, required=False, allow_blank=True)
    date_acquisition = serializers.DateField(required=False, allow_null=True)
    cout_achat       = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    fin_garantie     = serializers.DateField(required=False, allow_null=True)


# ── LOGICIEL ───────────────────────────────────────────────────────────

from .models import Logiciel, InstallationLogiciel

class LogicielListSerializer(serializers.ModelSerializer):
    nb_installations    = serializers.IntegerField(read_only=True)
    taux_utilisation_pct = serializers.FloatField(read_only=True)
    licence_expiree     = serializers.BooleanField(read_only=True)
    alerte_expiration   = serializers.BooleanField(read_only=True)
    type_licence_display = serializers.CharField(source='get_type_licence_display', read_only=True)

    class Meta:
        model = Logiciel
        fields = [
            'id', 'nom', 'editeur', 'version',
            'type_licence', 'type_licence_display',
            'nb_postes_autorises', 'nb_installations', 'taux_utilisation_pct',
            'cout_annuel', 'date_expiration',
            'licence_expiree', 'alerte_expiration',
            'cree_le',
        ]


class LogicielDetailSerializer(serializers.ModelSerializer):
    nb_installations     = serializers.IntegerField(read_only=True)
    taux_utilisation_pct = serializers.FloatField(read_only=True)
    licence_expiree      = serializers.BooleanField(read_only=True)
    alerte_expiration    = serializers.BooleanField(read_only=True)
    type_licence_display = serializers.CharField(source='get_type_licence_display', read_only=True)

    class Meta:
        model = Logiciel
        fields = [
            'id', 'nom', 'editeur', 'version',
            'type_licence', 'type_licence_display',
            'nb_postes_autorises', 'nb_installations', 'taux_utilisation_pct',
            'cout_annuel', 'date_achat', 'date_expiration',
            'licence_expiree', 'alerte_expiration',
            'alerte_active', 'jours_alerte',
            'notes', 'cree_le', 'modifie_le',
        ]
        # cle_licence volontairement exclue du serializer de lecture
        # — exposée uniquement via un endpoint dédié sécurisé


class LogicielWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Logiciel
        fields = [
            'nom', 'editeur', 'version', 'type_licence',
            'nb_postes_autorises', 'cout_annuel',
            'date_achat', 'date_expiration',
            'alerte_active', 'jours_alerte',
            'cle_licence', 'notes',
        ]

    def validate(self, attrs):
        # Une licence perpétuelle ne devrait pas avoir de date d'expiration
        if (attrs.get('type_licence') == 'perpetuelle'
                and attrs.get('date_expiration')):
            raise serializers.ValidationError({
                'date_expiration': "Une licence perpétuelle ne peut pas avoir de date d'expiration."
            })
        return attrs


# ── INSTALLATION LOGICIEL ──────────────────────────────────────────────

class InstallationLogicielSerializer(serializers.ModelSerializer):
    logiciel_nom      = serializers.CharField(source='logiciel.nom', read_only=True)
    logiciel_editeur  = serializers.CharField(source='logiciel.editeur', read_only=True)
    equipement_tag    = serializers.CharField(source='equipement.tag_inventaire', read_only=True)
    equipement_nom    = serializers.CharField(source='equipement.nom', read_only=True)
    installe_par_nom  = serializers.SerializerMethodField()

    class Meta:
        model = InstallationLogiciel
        fields = [
            'id',
            'logiciel', 'logiciel_nom', 'logiciel_editeur',
            'equipement', 'equipement_tag', 'equipement_nom',
            'version_installee', 'date_installation',
            'installe_par', 'installe_par_nom',
            'notes', 'cree_le',
        ]
        read_only_fields = ['id', 'cree_le']

    def get_installe_par_nom(self, obj):
        if obj.installe_par:
            return obj.installe_par.nom_complet
        return None


class InstallationLogicielWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstallationLogiciel
        fields = ['logiciel', 'equipement', 'version_installee', 'date_installation', 'notes']

    def validate(self, attrs):
        logiciel   = attrs['logiciel']
        equipement = attrs['equipement']

        # Doublon
        if InstallationLogiciel.objects.filter(
            logiciel=logiciel, equipement=equipement
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                f"'{logiciel.nom}' est déjà installé sur {equipement.tag_inventaire}."
            )

        # Quota
        if logiciel.nb_postes_autorises is not None:
            count = logiciel.installations.exclude(
                pk=self.instance.pk if self.instance else None
            ).count()
            if count >= logiciel.nb_postes_autorises:
                raise serializers.ValidationError(
                    f"Quota atteint pour '{logiciel.nom}' "
                    f"({logiciel.nb_postes_autorises} postes max, {count} installés)."
                )
        return attrs
