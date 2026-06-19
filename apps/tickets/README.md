# Module Tickets — ITSM Backend

## Installation

```bash
pip install djangorestframework-nested django-filter celery
```

Ajouter au `INSTALLED_APPS` :
```python
"tickets",
"django_filters",
```

Ajouter aux `urls.py` principal :
```python
path("api/v1/", include("tickets.urls")),
```

---

## Cycle de vie des tickets

```
NOUVEAU → ASSIGNE → EN_COURS → RESOLU → FERME
                ↘ EN_ATTENTE ↗      ↘ EN_COURS (réouverture)
         ANNULE (depuis n'importe quel état ouvert)
```

Endpoint de transition : `POST /api/v1/tickets/{id}/transition/`
```json
{ "nouveau_statut": "assigne", "commentaire": "Pris en charge" }
```

---

## Endpoints complets

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/api/v1/tickets/` | Liste avec filtres |
| POST | `/api/v1/tickets/` | Créer un ticket |
| GET | `/api/v1/tickets/{id}/` | Détail complet |
| PATCH | `/api/v1/tickets/{id}/` | Mise à jour |
| DELETE | `/api/v1/tickets/{id}/` | Suppression (admin) |
| POST | `/api/v1/tickets/{id}/transition/` | Changer statut |
| POST | `/api/v1/tickets/{id}/cloturer/` | Clôturer + solution |
| POST | `/api/v1/tickets/{id}/escalader/` | Escalader |
| POST | `/api/v1/tickets/{id}/assigner/` | Assigner technicien |
| GET | `/api/v1/tickets/stats/` | Statistiques |
| GET | `/api/v1/tickets/mes-tickets/` | Mes tickets |
| GET/POST | `/api/v1/tickets/{id}/commentaires/` | Commentaires |
| GET/POST | `/api/v1/tickets/{id}/pieces-jointes/` | Fichiers joints |
| GET/POST | `/api/v1/tickets/{id}/interventions/` | Temps passé |
| GET | `/api/v1/tickets/{id}/historique/` | Audit trail |
| CRUD | `/api/v1/kb/` | Base de connaissances |
| POST | `/api/v1/kb/{id}/publier/` | Publier/dépublier |
| POST | `/api/v1/kb/{id}/voter/` | Vote utilité |
| GET | `/api/v1/notifications/non-lues/` | Notifs non lues |
| POST | `/api/v1/notifications/marquer-tout-lu/` | Tout marquer lu |
| CRUD | `/api/v1/sla/` | Config SLA (admin) |
| CRUD | `/api/v1/categories/` | Catégories |

---

## Filtres disponibles (`GET /api/v1/tickets/`)

| Paramètre | Exemple |
|-----------|---------|
| `statut` | `?statut=nouveau&statut=assigne` |
| `priorite` | `?priorite=critique` |
| `type_ticket` | `?type_ticket=incident` |
| `assigne_a` | `?assigne_a={uuid}` |
| `demandeur` | `?demandeur={uuid}` |
| `equipement` | `?equipement={uuid}` |
| `escalade` | `?escalade=true` |
| `sla_depasse` | `?sla_depasse=true` |
| `non_assigne` | `?non_assigne=true` |
| `search` | `?search=imprimante` |
| `ordering` | `?ordering=-priorite` |

---

## Configuration SLA par défaut

| Priorité | Prise en charge | Résolution |
|----------|----------------|------------|
| Critique | 15 min | 4h |
| Haute | 1h | 8h |
| Moyenne | 4h | 24h |
| Basse | 8h | 72h |

---

## Celery (surveillance SLA)

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "surveiller-sla": {
        "task": "tickets.tasks.surveiller_sla",
        "schedule": crontab(minute="*/15"),
    },
    "fermer-resolus": {
        "task": "tickets.tasks.fermer_tickets_resolus",
        "schedule": crontab(hour="0", minute="0"),  # chaque nuit à minuit
        "kwargs": {"jours": 7},
    },
}
```

---

## Migrations

```bash
python manage.py makemigrations tickets
python manage.py migrate
```

La migration `0002_seed_sla` charge automatiquement les 4 configurations SLA par défaut.
