import django_filters
from django.utils import timezone
from .models import Ticket, Statut, Priorite, TypeTicket


class TicketFilter(django_filters.FilterSet):
    statut      = django_filters.MultipleChoiceFilter(choices=Statut.choices)
    priorite    = django_filters.MultipleChoiceFilter(choices=Priorite.choices)
    type_ticket = django_filters.MultipleChoiceFilter(choices=TypeTicket.choices)
    categorie   = django_filters.UUIDFilter(field_name="categorie__id")
    assigne_a   = django_filters.UUIDFilter(field_name="assigne_a__id")
    demandeur   = django_filters.UUIDFilter(field_name="demandeur__id")
    equipement  = django_filters.UUIDFilter(field_name="equipement__id")
    escalade    = django_filters.BooleanFilter()

    # Filtres SLA
    sla_depasse = django_filters.BooleanFilter(method="filter_sla_depasse")
    non_assigne = django_filters.BooleanFilter(method="filter_non_assigne")

    # Plages de dates
    cree_apres  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    cree_avant  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = Ticket
        fields = [
            "statut", "priorite", "type_ticket", "categorie",
            "assigne_a", "demandeur", "equipement", "escalade",
        ]

    def filter_sla_depasse(self, queryset, name, value):
        now = timezone.now()
        ouverts = ["nouveau", "assigne", "en_cours", "en_attente"]
        if value:
            return queryset.filter(echeance_resolution__lt=now, statut__in=ouverts)
        return queryset.exclude(echeance_resolution__lt=now, statut__in=ouverts)

    def filter_non_assigne(self, queryset, name, value):
        if value:
            return queryset.filter(assigne_a=None)
        return queryset.exclude(assigne_a=None)
