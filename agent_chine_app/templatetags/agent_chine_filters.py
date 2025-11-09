"""
Template filters personnalisés pour Agent Chine
"""
from django import template
from notifications_app.utils import format_cfa as format_cfa_util

register = template.Library()


@register.filter(name='cfa')
def format_cfa_filter(value):
    """
    Formatte un nombre en FCFA avec séparateurs de milliers
    
    Exemples:
    - 1500 -> "1 500"
    - 1200000.4 -> "1 200 000"
    - {{ colis.prix_calcule|cfa }} -> "18 000"
    
    Usage dans template:
    {% load agent_chine_filters %}
    {{ montant|cfa }} FCFA
    """
    return format_cfa_util(value)


@register.filter(name='cfa_with_currency')
def format_cfa_with_currency(value):
    """
    Formatte un nombre en FCFA avec séparateurs de milliers + devise
    
    Exemples:
    - 1500 -> "1 500 FCFA"
    - 1200000.4 -> "1 200 000 FCFA"
    
    Usage dans template:
    {% load agent_chine_filters %}
    {{ montant|cfa_with_currency }}
    """
    return f"{format_cfa_util(value)} FCFA"
