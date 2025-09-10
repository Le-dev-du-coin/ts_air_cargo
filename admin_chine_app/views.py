from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q

from authentication.models import CustomUser
from agent_chine_app.models import Client, Lot, Colis
from .models import InventoryChina, OperationChina


def admin_chine_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est un admin Chine
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authentication:role_based_login', role='admin_chine')
        if not getattr(request.user, 'is_admin_chine', False):
            messages.error(request, "Accès refusé. Vous devez être administrateur Chine.")
            return redirect('authentication:home')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_chine_required
def dashboard(request):
    """
    Dashboard principal de l'admin Chine avec statistiques complètes
    Conforme à la règle dashboard (statuts parcelles/lots Chine & Mali)
    """
    today = timezone.now().date()
    current_month = today.replace(day=1)
    yesterday = today - timezone.timedelta(days=1)

    # Statistiques générales
    total_clients = Client.objects.count()
    total_lots = Lot.objects.count()
    total_colis = Colis.objects.count()

    # Statuts lots
    lots_stats = {
        'ouverts': Lot.objects.filter(statut='ouvert').count(),
        'fermes': Lot.objects.filter(statut='ferme').count(),
        'expedies': Lot.objects.filter(statut='expedie').count(),
        'en_transit': Lot.objects.filter(statut='en_transit').count(),
        'arrives': Lot.objects.filter(statut='arrive').count(),
        'livres': Lot.objects.filter(statut='livre').count(),
    }

    # Statuts colis
    colis_stats = {
        'en_attente': Colis.objects.filter(statut='en_attente').count(),
        'receptionnes_chine': Colis.objects.filter(statut='receptionne_chine').count(),
        'en_transit': Colis.objects.filter(statut='en_transit').count(),
        'arrives_mali': Colis.objects.filter(statut='arrive').count(),
        'livres': Colis.objects.filter(statut='livre').count(),
        'perdus': Colis.objects.filter(statut='perdu').count(),
    }

    # Valeurs financières colis
    valeurs_colis = Colis.objects.aggregate(
        valeur_totale=Sum('prix_calcule'),
        valeur_stock_chine=Sum('prix_calcule', filter=Q(statut__in=['en_attente', 'receptionne_chine'])),
        valeur_transit=Sum('prix_calcule', filter=Q(statut='en_transit')),
        valeur_arrives_mali=Sum('prix_calcule', filter=Q(statut='arrive')),
        valeur_livres=Sum('prix_calcule', filter=Q(statut='livre')),
    )

    # Prix des lots
    prix_lots = Lot.objects.aggregate(
        prix_transport_total=Sum('prix_transport'),
        prix_lots_expedies=Sum('prix_transport', filter=Q(statut='expedie')),
        prix_lots_en_transit=Sum('prix_transport', filter=Q(statut='en_transit')),
    )

    # Inventaire Chine
    try:
        inv_stats = {
            'nb_produits': InventoryChina.objects.count(),
            'valeur_stock_yuan': sum((p.valeur_stock_yuan or 0) for p in InventoryChina.objects.all()),
            'valeur_stock_fcfa': sum((p.valeur_stock_fcfa or 0) for p in InventoryChina.objects.all()),
            'produits_low_stock': InventoryChina.objects.filter(quantite_stock__lte=models.F('quantite_minimale')).count(),
        }
    except:
        inv_stats = {
            'nb_produits': 0,
            'valeur_stock_yuan': 0,
            'valeur_stock_fcfa': 0,
            'produits_low_stock': 0,
        }

    # Opérations récentes
    try:
        operations_recentes = OperationChina.objects.order_by('-date_operation')[:5]
    except:
        operations_recentes = []

    context = {
        'title': 'Dashboard Admin Chine',
        'total_clients': total_clients,
        'total_lots': total_lots,
        'total_colis': total_colis,
        'lots_stats': lots_stats,
        'colis_stats': colis_stats,
        'valeurs_colis': valeurs_colis,
        'prix_lots': prix_lots,
        'inv_stats': inv_stats,
        'operations_recentes': operations_recentes,
        'today': today,
    }
    return render(request, 'admin_chine_app/dashboard.html', context)
