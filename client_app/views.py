from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Sum, Q
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
import json

from notifications_app.models import Notification
from django.contrib.auth import get_user_model
from .models import Client as ClientModel

User = get_user_model()

# Décorateur pour vérifier que l'utilisateur est un client
def client_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authentication:role_based_login', role='client')
        
        # Vérifier que l'utilisateur a le rôle client
        if not hasattr(request.user, 'role') or request.user.role != 'client':
            messages.error(request, "Accès refusé. Vous devez être un client.")
            return redirect('authentication:role_based_login', role='client')
        
        # Créer automatiquement le profil client s'il n'existe pas
        try:
            client = ClientModel.objects.get(user=request.user)
        except ClientModel.DoesNotExist:
            # Créer le profil client automatiquement avec les données de l'utilisateur
            client = ClientModel.objects.create(
                user=request.user,
                telephone=request.user.telephone,
                adresse="Adresse à compléter",
                pays="ML"  # Mali par défaut
            )
            messages.info(request, "Votre profil client a été créé automatiquement. Veuillez compléter vos informations.")
        
        return view_func(request, *args, **kwargs)
    return wrapper

@client_required
def dashboard_view(request):
    """
    Tableau de bord client avec statistiques personnelles et données réelles
    """
    try:
        client = ClientModel.objects.get(user=request.user)
    except ClientModel.DoesNotExist:
        messages.error(request, "Profil client non trouvé. Contactez l'administration.")
        return redirect('authentication:login_client')
    
    # Importer le modèle Colis depuis agent_chine_app
    from agent_chine_app.models import Colis, Client as ChineClient
    
    # Récupérer le client Chine correspondant
    try:
        chine_client = ChineClient.objects.get(
            user__telephone=client.telephone
        )
        
        # Statistiques réelles basées sur les colis du client
        mes_colis = Colis.objects.filter(client=chine_client)
        
        stats = {
            'total_colis': mes_colis.count(),
            'en_chine': mes_colis.filter(statut='receptionne_chine').count(),
            'en_transit': mes_colis.filter(statut__in=['expedie', 'en_transit']).count(),
            'arrive_mali': mes_colis.filter(statut='arrive').count(),
            'livres': mes_colis.filter(statut='livre').count(),
            'perdus': mes_colis.filter(statut='perdu').count(),
        }
        
        # Derniers colis (5 plus récents)
        derniers_colis = mes_colis.select_related('lot').order_by('-date_creation')[:5]
        
        # Colis en cours (pas encore livrés)
        colis_en_cours = mes_colis.filter(
            statut__in=['receptionne_chine', 'expedie', 'en_transit', 'arrive']
        ).select_related('lot').order_by('-date_creation')[:10]
        
        # Calcul de la valeur totale des colis
        valeur_totale = mes_colis.aggregate(
            total=Sum('prix_calcule')
        )['total'] or 0.0
        
        # Notifications non lues
        notifications_non_lues = Notification.objects.filter(
            destinataire=request.user,
            statut='non_lu'
        ).count()
        
    except ChineClient.DoesNotExist:
        # Client pas encore créé dans le système Chine
        stats = {
            'total_colis': 0,
            'en_chine': 0,
            'en_transit': 0,
            'arrive_mali': 0,
            'livres': 0,
            'perdus': 0,
        }
        derniers_colis = []
        colis_en_cours = []
        valeur_totale = 0.0
        notifications_non_lues = 0
    
    # Vérifier si c'est la première connexion (profil créé récemment)
    from datetime import timedelta
    is_first_login = False
    if client.date_creation and (timezone.now() - client.date_creation) < timedelta(minutes=5):
        is_first_login = True
    
    # Vérifier si l'utilisateur utilise encore le mot de passe par défaut
    # (on peut supposer que si last_login est très récent par rapport à date_joined, c'est potentiellement le cas)
    show_password_reminder = False
    if request.user.last_login and request.user.date_joined:
        if (request.user.last_login - request.user.date_joined) < timedelta(hours=1):
            show_password_reminder = True
    
    context = {
        'stats': stats,
        'derniers_colis': derniers_colis,
        'colis_en_cours': colis_en_cours,
        'notifications_non_lues': notifications_non_lues,
        'valeur_totale': float(valeur_totale),
        'client': client,
        'is_first_login': is_first_login,
        'show_password_reminder': show_password_reminder,
        'title': 'Dashboard Client'
    }
    
    return render(request, 'client_app/dashboard.html', context)

@client_required
def mes_colis_view(request):
    """
    Liste complète des colis du client avec filtres et recherche
    """
    try:
        client = ClientModel.objects.get(user=request.user)
    except ClientModel.DoesNotExist:
        messages.error(request, "Profil client non trouvé.")
        return redirect('authentication:login_client')
    
    # Importer le modèle Colis depuis agent_chine_app
    from agent_chine_app.models import Colis, Client as ChineClient
    
    try:
        chine_client = ChineClient.objects.get(
            user__telephone=client.telephone
        )
        
        # Récupérer tous les colis du client
        colis_queryset = Colis.objects.filter(
            client=chine_client
        ).select_related('lot').order_by('-date_creation')
        
        # Filtres
        statut_filter = request.GET.get('statut', '')
        search_query = request.GET.get('search', '')
        date_debut = request.GET.get('date_debut', '')
        date_fin = request.GET.get('date_fin', '')
        
        # Application des filtres
        if statut_filter:
            colis_queryset = colis_queryset.filter(statut=statut_filter)
        
        if search_query:
            colis_queryset = colis_queryset.filter(
                Q(numero_suivi__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(lot__numero_lot__icontains=search_query)
            )
        
        if date_debut:
            try:
                date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d')
                colis_queryset = colis_queryset.filter(date_creation__gte=date_debut_obj)
            except ValueError:
                pass
        
        if date_fin:
            try:
                date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d')
                colis_queryset = colis_queryset.filter(date_creation__lte=date_fin_obj)
            except ValueError:
                pass
        
        # Pagination
        paginator = Paginator(colis_queryset, 12)  # 12 colis par page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistiques rapides
        total_colis = colis_queryset.count()
        valeur_totale = colis_queryset.aggregate(
            total=Sum('prix_calcule')
        )['total'] or 0.0
        
    except ChineClient.DoesNotExist:
        # Client pas encore créé dans le système Chine
        page_obj = None
        total_colis = 0
        valeur_totale = 0.0
        statut_filter = request.GET.get('statut', '')
        search_query = request.GET.get('search', '')
        date_debut = request.GET.get('date_debut', '')
        date_fin = request.GET.get('date_fin', '')
    
    # Choix de statuts pour le filtre
    STATUT_CHOICES = [
        ('', 'Tous les statuts'),
        ('receptionne_chine', 'Réceptionné en Chine'),
        ('expedie', 'Expédié'),
        ('en_transit', 'En Transit'),
        ('arrive', 'Arrivé au Mali'),
        ('livre', 'Livré'),
        ('perdu', 'Perdu'),
    ]
    
    context = {
        'page_obj': page_obj,
        'colis': page_obj.object_list if page_obj else [],
        'total_colis': total_colis,
        'valeur_totale': float(valeur_totale),
        'statut_filter': statut_filter,
        'search_query': search_query,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'statut_choices': STATUT_CHOICES,
        'client': client,
        'title': 'Mes Colis'
    }
    
    return render(request, 'client_app/mes_colis.html', context)

@client_required
def colis_detail_view(request, colis_id):
    """
    Détail d'un colis avec historique et timeline
    """
    try:
        client = ClientModel.objects.get(user=request.user)
    except ClientModel.DoesNotExist:
        messages.error(request, "Profil client non trouvé.")
        return redirect('authentication:login_client')
    
    # Importer le modèle Colis depuis agent_chine_app
    from agent_chine_app.models import Colis, Client as ChineClient
    
    try:
        chine_client = ChineClient.objects.get(
            user__telephone=client.telephone
        )
        
        # Récupérer le colis
        colis = get_object_or_404(
            Colis.objects.select_related('lot', 'client__user'),
            id=colis_id,
            client=chine_client
        )
        
        # Timeline du colis (statuts chronologiques)
        timeline = []
        
        # Réceptionné en Chine
        if colis.date_creation:
            timeline.append({
                'statut': 'receptionne_chine',
                'libelle': 'Réceptionné en Chine',
                'date': colis.date_creation,
                'description': 'Votre colis a été reçu et enregistré dans notre entrepôt en Chine',
                'icone': 'fas fa-check-circle',
                'couleur': 'success',
                'complete': True
            })
        
        # Expédié
        if colis.lot.date_expedition:
            timeline.append({
                'statut': 'expedie',
                'libelle': 'Expédié de Chine',
                'date': colis.lot.date_expedition,
                'description': f'Colis expédié dans le lot {colis.lot.numero_lot}',
                'icone': 'fas fa-plane',
                'couleur': 'info',
                'complete': colis.statut in ['expedie', 'en_transit', 'arrive', 'livre']
            })
        
        # En transit
        if colis.statut in ['en_transit', 'arrive', 'livre']:
            timeline.append({
                'statut': 'en_transit',
                'libelle': 'En Transit',
                'date': colis.lot.date_expedition,
                'description': 'Votre colis est en cours de transport vers le Mali',
                'icone': 'fas fa-shipping-fast',
                'couleur': 'warning',
                'complete': True
            })
        
        # Arrivé au Mali
        if colis.lot.date_arrivee and colis.statut in ['arrive', 'livre']:
            timeline.append({
                'statut': 'arrive',
                'libelle': 'Arrivé au Mali',
                'date': colis.lot.date_arrivee,
                'description': 'Votre colis est arrivé au Mali et est prêt pour la livraison',
                'icone': 'fas fa-map-marker-alt',
                'couleur': 'primary',
                'complete': True
            })
        
        # Livré
        if colis.statut == 'livre':
            timeline.append({
                'statut': 'livre',
                'libelle': 'Livré',
                'date': timezone.now(),  # Date approximative
                'description': 'Votre colis a été livré avec succès',
                'icone': 'fas fa-check',
                'couleur': 'success',
                'complete': True
            })
        
        # Trier par date
        timeline.sort(key=lambda x: x['date'])
        
        # Informations additionnelles
        infos_transport = {
            'origine': 'Chine',
            'destination': 'Mali - Bamako',
            'mode_transport': 'Maritime + Terrestre',
            'duree_estimee': '25-35 jours',
            'transporteur': 'TS Air Cargo',
        }
        
    except ChineClient.DoesNotExist:
        messages.error(request, "Aucun colis trouvé pour ce client.")
        return redirect('client_app:mes_colis')
    
    context = {
        'colis': colis,
        'timeline': timeline,
        'infos_transport': infos_transport,
        'client': client,
        'title': f'Détail Colis - {colis.numero_suivi}'
    }
    
    return render(request, 'client_app/colis_detail.html', context)

@client_required
def colis_image_view(request, colis_id):
    """
    Vue pour afficher l'image du colis en grand format
    """
    raise Http404("Image non disponible")

@client_required
def notifications_view(request):
    """
    Liste des notifications du client
    """
    return render(request, 'client_app/notifications.html', {'title': 'Notifications'})

@client_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """
    Marquer une notification comme lue
    """
    return JsonResponse({'success': True})

@client_required
def suivi_colis_view(request):
    """
    Page de suivi de colis (permet aussi de chercher des colis d'autres clients)
    """
    return render(request, 'client_app/suivi_colis.html', {'title': 'Suivi de Colis'})

@client_required
def suivi_detail_view(request, numero_suivi):
    """
    Détail du suivi d'un colis par numéro de suivi
    """
    return render(request, 'client_app/suivi_detail.html', {'title': f'Suivi - {numero_suivi}'})

@client_required
def change_password_view(request):
    """
    Vue pour changer le mot de passe du client
    """
    try:
        client = ClientModel.objects.get(user=request.user)
    except ClientModel.DoesNotExist:
        messages.error(request, "Profil client non trouvé.")
        return redirect('authentication:login_client')
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Votre mot de passe a été changé avec succès!')
            return redirect('client_app:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'client': client,
        'title': 'Changer le mot de passe'
    }
    
    return render(request, 'client_app/change_password.html', context)

@client_required
def settings_view(request):
    """
    Page des paramètres du client (notifications, préférences)
    """
    try:
        client = ClientModel.objects.get(user=request.user)
    except ClientModel.DoesNotExist:
        messages.error(request, "Profil client non trouvé.")
        return redirect('authentication:login_client')
    
    # Récupérer ou créer les paramètres de notification
    from .models import ClientNotificationSettings
    
    settings, created = ClientNotificationSettings.objects.get_or_create(
        client=client,
        defaults={
            'notifications_in_app': True,
            'notifications_whatsapp': False,
            'notifications_sms': False,
        }
    )
    
    if request.method == 'POST':
        # Récupérer les valeurs du formulaire
        notifications_in_app = request.POST.get('notifications_in_app') == 'on'
        notifications_whatsapp = request.POST.get('notifications_whatsapp') == 'on'
        notifications_sms = request.POST.get('notifications_sms') == 'on'
        
        # Logique d'exclusivité : si in_app est activé, on ne peut choisir qu'un seul autre
        if notifications_in_app and notifications_whatsapp and notifications_sms:
            messages.error(request, "Si les notifications in-app sont activées, vous ne pouvez choisir qu'un seul mode supplémentaire (WhatsApp OU SMS).")
        else:
            # Mettre à jour les paramètres
            settings.notifications_in_app = notifications_in_app
            settings.notifications_whatsapp = notifications_whatsapp
            settings.notifications_sms = notifications_sms
            settings.save()
            
            messages.success(request, "Vos préférences de notification ont été sauvegardées.")
            return redirect('client_app:settings')
    
    context = {
        'settings': settings,
        'client': client,
        'title': 'Paramètres'
    }
    
    return render(request, 'client_app/settings.html', context)

