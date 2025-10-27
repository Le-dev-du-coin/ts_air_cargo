from django import template
from django.db.models import Q

register = template.Library()

@register.filter
def filter_by_statut(queryset, statut):
    """
    Filtre un queryset de colis par statut
    Utilisation dans le template : {{ colis_queryset|filter_by_statut:'livre' }}
    """
    return queryset.filter(statut=statut)
