import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class RoleChoices(models.TextChoices):
    ADMIN = 'admin', 'Administrateur'
    RESP_IT = 'resp_it', 'Responsable IT'
    TECHNICIEN = 'technicien', 'Technicien'
    UTILISATEUR = 'utilisateur', 'Utilisateur final'


class UtilisateurManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        extra_fields.setdefault('role', RoleChoices.UTILISATEUR)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', RoleChoices.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('actif', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name='Adresse email')
    nom = models.CharField(max_length=100, verbose_name='Nom')
    prenom = models.CharField(max_length=100, verbose_name='Prénom')
    telephone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.UTILISATEUR,
        verbose_name='Rôle',
    )
    service = models.CharField(max_length=100, blank=True, verbose_name='Service')
    service_obj = models.ForeignKey('administration.Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='utilisateurs', verbose_name='Service')
    localisation = models.CharField(max_length=150, blank=True, verbose_name='Localisation')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    is_staff = models.BooleanField(default=False)
    derniere_connexion = models.DateTimeField(null=True, blank=True, verbose_name='Dernière connexion')
    cree_le = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    modifie_le = models.DateTimeField(auto_now=True, verbose_name='Modifié le')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']

    objects = UtilisateurManager()

    class Meta:
        db_table = 'utilisateurs'
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f'{self.prenom} {self.nom} <{self.email}>'

    @property
    def nom_complet(self):
        return f'{self.prenom} {self.nom}'

    @property
    def is_active(self):
        return self.actif

    def has_role(self, *roles):
        return self.role in roles

    @property
    def is_admin(self):
        return self.role == RoleChoices.ADMIN

    @property
    def is_technicien(self):
        return self.role in (RoleChoices.TECHNICIEN, RoleChoices.RESP_IT, RoleChoices.ADMIN)
