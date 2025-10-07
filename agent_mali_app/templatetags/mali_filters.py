from django import template
from decimal import Decimal
from django.db.models import Q

register = template.Library()

@register.filter
def sum_field(queryset, field_name):
    """
    Calcule la somme d'un champ spécifique dans un queryset
    Usage: {{ lots|sum_field:"poids" }}
    """
    try:
        total = sum(float(getattr(obj, field_name, 0)) for obj in queryset)
        return total
    except (ValueError, TypeError):
        return 0

@register.filter
def unique_clients(colis_list):
    """
    Retourne une liste des clients uniques à partir d'une liste de colis
    Usage: {{ colis|unique_clients|length }}
    """
    try:
        client_ids = set()
        unique_clients = []
        
        for colis in colis_list:
            if hasattr(colis, 'client') and colis.client.id not in client_ids:
                client_ids.add(colis.client.id)
                unique_clients.append(colis.client)
        
        return unique_clients
    except:
        return []

@register.filter
def get_category_color(category):
    """
    Retourne la couleur Bootstrap associée à une catégorie de dépense
    Usage: {{ depense.categorie|get_category_color }}
    """
    color_map = {
        'transport': 'primary',
        'personnel': 'success', 
        'materiel': 'info',
        'communication': 'warning',
        'carburant': 'danger',
        'reparation': 'secondary',
        'douane': 'dark',
        'stockage': 'light',
        'autre': 'muted'
    }
    return color_map.get(category, 'secondary')

@register.filter
def get_rapport_color(rapport_type):
    """
    Retourne la couleur Bootstrap associée à un type de rapport
    Usage: {{ rapport.type|get_rapport_color }}
    """
    color_map = {
        'daily': 'primary',
        'weekly': 'success',
        'monthly': 'info', 
        'yearly': 'warning',
        'custom': 'secondary'
    }
    return color_map.get(rapport_type, 'secondary')

@register.filter
def format_phone(phone_number):
    """
    Formate un numéro de téléphone pour WhatsApp (retire le +)
    Usage: {{ phone|format_phone }}
    """
    if phone_number:
        return str(phone_number).replace('+', '').replace(' ', '')
    return ''

@register.filter
def multiply(value, factor):
    """
    Multiplie une valeur par un facteur
    Usage: {{ price|multiply:1.18 }}
    """
    try:
        return float(value) * float(factor)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """
    Calcule le pourcentage d'une valeur par rapport au total
    Usage: {{ value|percentage:total }}
    """
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.simple_tag
def get_monthly_stats(user, month=None, year=None):
    """
    Récupère les statistiques mensuelles pour un utilisateur
    Usage: {% get_monthly_stats user as stats %}
    """
    from datetime import date
    from django.db.models import Sum, Count
    from ..models import Depense, Livraison
    
    if not month or not year:
        today = date.today()
        month = today.month
        year = today.year
    
    # Dépenses du mois
    depenses_mois = Depense.objects.filter(
        agent=user,
        date_depense__month=month,
        date_depense__year=year
    ).aggregate(
        total=Sum('montant'),
        count=Count('id')
    )
    
    # Livraisons du mois
    livraisons_mois = Livraison.objects.filter(
        agent_livreur=user,
        date_livraison_effective__month=month,
        date_livraison_effective__year=year,
        statut='livree'
    ).aggregate(
        total=Sum('montant_collecte'),
        count=Count('id')
    )
    return {
        'depenses_total': depenses_mois['total'] or 0,
        'depenses_count': depenses_mois['count'] or 0,
        'revenus_total': livraisons_mois['total'] or 0,
        'livraisons_count': livraisons_mois['count'] or 0
    }

@register.filter
def filter_by_statut(queryset, statut):
    """
    Filtre un queryset de colis par statut
    Usage: {{ colis_queryset|filter_by_statut:'livre' }}
    """
    return queryset.filter(statut=statut)

@register.filter
def stat_card(title, value, icon, color='primary', subtitle=None):
    """
    Génère une carte de statistique
    Usage: {% stat_card "Revenus" "50000 CFA" "bi-cash" "success" %}
    """
    return {
        'title': title,
        'value': value,
        'icon': icon,
        'color': color,
        'subtitle': subtitle
    }
