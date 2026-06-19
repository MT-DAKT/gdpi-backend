# ITSM Pro — Backend Django REST Framework

## Stack
- Python 3.11+
- Django 5.0
- Django REST Framework 3.15
- SimpleJWT (authentification JWT)
- PostgreSQL
- drf-spectacular (Swagger / OpenAPI)

## Installation

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (DB, SECRET_KEY…)

# 4. Créer la base de données PostgreSQL
psql -U postgres -c "CREATE USER itsm_user WITH PASSWORD 'itsm_pass';"
psql -U postgres -c "CREATE DATABASE itsm_db OWNER itsm_user;"

# 5. Appliquer les migrations
python manage.py migrate

# 6. Créer le superutilisateur
python manage.py createsuperuser

# 7. Lancer le serveur
python manage.py runserver
```

## Endpoints — Module Utilisateurs

### Authentification
| Méthode | URL | Description | Auth |
|---------|-----|-------------|------|
| POST | `/api/v1/users/auth/login/` | Connexion, retourne access + refresh | Public |
| POST | `/api/v1/users/auth/logout/` | Révocation du refresh token | JWT |
| POST | `/api/v1/users/auth/token/refresh/` | Renouveler l'access token | Public |
| GET/PATCH | `/api/v1/users/auth/me/` | Profil de l'utilisateur connecté | JWT |
| PUT | `/api/v1/users/auth/change-password/` | Changer son propre mot de passe | JWT |

### CRUD Utilisateurs (admin)
| Méthode | URL | Description | Rôle requis |
|---------|-----|-------------|-------------|
| GET | `/api/v1/users/` | Liste paginée + filtres | Admin, Resp IT |
| POST | `/api/v1/users/` | Créer un compte | Admin |
| GET | `/api/v1/users/{id}/` | Détail d'un utilisateur | Admin, Resp IT |
| PATCH | `/api/v1/users/{id}/` | Modifier un utilisateur | Admin |
| DELETE | `/api/v1/users/{id}/` | Désactiver (soft delete) | Admin |
| POST | `/api/v1/users/{id}/activer/` | Réactiver un compte | Admin |
| POST | `/api/v1/users/{id}/desactiver/` | Désactiver un compte | Admin |
| POST | `/api/v1/users/{id}/reset-password/` | Réinitialiser le mot de passe | Admin |
| PATCH | `/api/v1/users/{id}/changer-role/` | Changer le rôle | Admin |
| GET | `/api/v1/users/techniciens/` | Liste des techniciens actifs | JWT |
| GET | `/api/v1/users/stats/` | Statistiques du tableau de bord | JWT |

## Exemple de login

```bash
curl -X POST http://localhost:8000/api/v1/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@itsm.ml", "password": "motdepasse"}'
```

Réponse :
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "admin@itsm.ml",
    "nom_complet": "Amadou Maïga",
    "role": "admin",
    "service": "Informatique"
  }
}
```

## Documentation API interactive
- Swagger UI : http://localhost:8000/api/docs/
- ReDoc      : http://localhost:8000/api/redoc/
- Schema OpenAPI : http://localhost:8000/api/schema/

## Structure du projet
```
itsm_backend/
├── config/
│   ├── settings.py      # Configuration Django
│   ├── urls.py          # Routes racines
│   └── wsgi.py
├── apps/
│   └── users/
│       ├── models.py       # Modèle Utilisateur custom
│       ├── serializers.py  # JWT + CRUD serializers
│       ├── views.py        # ViewSet + vues auth
│       ├── permissions.py  # IsAdmin, IsAdminOrRespIT…
│       ├── urls.py         # Routes du module
│       └── admin.py        # Interface admin Django
├── requirements.txt
├── manage.py
└── .env.example
```

## Rôles et permissions
| Rôle | Code | Accès |
|------|------|-------|
| Administrateur | `admin` | Accès total |
| Responsable IT | `resp_it` | Lecture utilisateurs, gestion tickets/parc |
| Technicien | `technicien` | Traitement tickets, mise à jour inventaire |
| Utilisateur final | `utilisateur` | Création tickets, lecture son profil |
