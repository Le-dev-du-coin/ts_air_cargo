from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from .models import Client, Lot, Colis
from reporting_app.models import ShippingPrice
from notifications_app.models import Notification
from .client_management import ClientAccountManager, send_client_credentials
from django.contrib.auth import get_user_model
from notifications_app.services import NotificationService

User = get_user_model()

# Décorateur pour vérifier que l'utilisateur est un agent chine
def agent_chine_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_agent_chine:
            messages.error(request, "Accès refusé. Vous devez être un agent en Chine.")
            return redirect('authentication:login_agent_chine')
        return view_func(request, *args, **kwargs)
    return wrapper

@agent_chine_required
def dashboard_view(request):
    """
    Tableau de bord pour Agent Chine avec statistiques dynamiques
    """
    from datetime import datetime, timedelta
    from django.db.models import Sum, Avg
    
    # Statistiques générales
    total_clients = Client.objects.count()
    total_lots = Lot.objects.count()
    total_colis = Colis.objects.count()
    
    # Lots par statut
    lots_ouverts = Lot.objects.filter(statut='ouvert').count()
    lots_fermes = Lot.objects.filter(statut='ferme').count()
    lots_expedies = Lot.objects.filter(statut='expedie').count()
    
    # Colis par statut
    colis_recus = Colis.objects.filter(statut='receptionne_chine').count()
    colis_en_transit = Colis.objects.filter(statut='en_transit').count()
    colis_en_attente = Colis.objects.filter(statut='en_attente').count()
    
    # Calculs de revenus
    revenus_mois = 0
    total_revenus = 0
    try:
        # Revenus du mois courant (prix de transport des lots fermés/expédiés)
        debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        lots_facturable_mois = Lot.objects.filter(
            statut__in=['ferme', 'expedie'],
            date_fermeture__gte=debut_mois
        )
        revenus_mois = sum(float(lot.prix_transport or 0) for lot in lots_facturable_mois)
        
        # Total revenus de tous les lots fermés/expédiés
        lots_facturable_total = Lot.objects.filter(statut__in=['ferme', 'expedie'])
        total_revenus = sum(float(lot.prix_transport or 0) for lot in lots_facturable_total)
    except Exception as e:
        # Erreur lors du calcul des revenus - ignorée silencieusement
        pass
    
    # Statistiques de croissance (simulation basée sur l'activité récente)
    try:
        # Comparer avec le mois précédent
        debut_mois_precedent = (debut_mois - timedelta(days=30)).replace(day=1)
        fin_mois_precedent = debut_mois - timedelta(days=1)
        
        clients_mois_precedent = Client.objects.filter(
            date_creation__gte=debut_mois_precedent,
            date_creation__lte=fin_mois_precedent
        ).count()
        
        clients_ce_mois = Client.objects.filter(date_creation__gte=debut_mois).count()
        
        # Calcul pourcentage croissance clients
        if clients_mois_precedent > 0:
            croissance_clients = ((clients_ce_mois - clients_mois_precedent) / clients_mois_precedent) * 100
        else:
            croissance_clients = 100 if clients_ce_mois > 0 else 0
    except:
        croissance_clients = 5.8  # Valeur par défaut
    
    # Derniers lots créés
    derniers_lots = Lot.objects.select_related().prefetch_related('colis').order_by('-date_creation')[:5]
    
    # Derniers colis créés
    derniers_colis = Colis.objects.select_related('client__user', 'lot').order_by('-date_creation')[:5]
    
    context = {
        'stats': {
            'total_clients': total_clients,
            'total_lots': total_lots,
            'total_colis': total_colis,
            'lots_ouverts': lots_ouverts,
            'lots_fermes': lots_fermes,
            'lots_expedies': lots_expedies,
            'colis_recus': colis_recus,
            'colis_en_transit': colis_en_transit,
            'colis_en_attente': colis_en_attente,
            'revenus_mois': revenus_mois,
            'total_revenus': total_revenus,
            'croissance_clients': croissance_clients,
        },
        'derniers_lots': derniers_lots,
        'derniers_colis': derniers_colis,
    }
    return render(request, 'agent_chine_app/dashboard.html', context)

@agent_chine_required
def client_list_view(request):
    """
    Liste des clients avec recherche et pagination
    """
    clients = Client.objects.all().order_by('-date_creation')
    
    # Recherche
    search_query = request.GET.get('search', '')
    if search_query:
        clients = clients.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__telephone__icontains=search_query) |
            Q(adresse__icontains=search_query)
        )
    
    context = {
        'clients': clients,
        'search_query': search_query,
    }
    return render(request, 'agent_chine_app/client_list.html', context)

@agent_chine_required
def client_create_view(request):
    """
    Création d'un nouveau client avec compte utilisateur automatique
    """
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            telephone = request.POST.get('telephone')
            first_name = request.POST.get('first_name') or request.POST.get('prenom')
            last_name = request.POST.get('last_name') or request.POST.get('nom')
            email = request.POST.get('email', '')
            adresse = request.POST.get('adresse')
            pays = request.POST.get('pays', 'ML')
            password = request.POST.get('password')  # Mot de passe saisi par l'agent
            
            # Créer ou récupérer le compte utilisateur avec mot de passe personnalisé
            result = ClientAccountManager.get_or_create_client_with_password(
                telephone=telephone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                notify=True
            )
            
            # Créer ou mettre à jour le profil client
            client, client_created = Client.objects.get_or_create(
                user=result['client'],
                defaults={
                    'adresse': adresse,
                    'pays': pays
                }
            )
            
            if not client_created:
                # Mettre à jour les informations existantes
                client.adresse = adresse
                client.pays = pays
                client.save()
            
            if result['created']:
                messages.success(request, f"✅ Nouveau client créé: {result['client'].get_full_name()}. Identifiants envoyés par WhatsApp.")
            else:
                messages.info(request, f"ℹ️ Client existant mis à jour: {result['client'].get_full_name()}")
                
            return redirect('agent_chine:client_detail', client_id=client.id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la création du client: {str(e)}")
    
    context = {
        'title': 'Nouveau Client',
        'submit_text': 'Créer',
        'countries': Client._meta.get_field('pays').choices,
    }
    return render(request, 'agent_chine_app/client_form.html', context)

@agent_chine_required
def client_detail_view(request, client_id):
    """
    Détail d'un client avec ses colis et statistiques
    """
    client = get_object_or_404(Client, id=client_id)
    colis = client.colis.all().order_by('-date_creation')
    
    # Calculer les statistiques de colis par statut
    total_colis = colis.count()
    colis_livres = colis.filter(statut='livre_mali').count()
    colis_en_transit = colis.filter(statut='en_transit').count()
    
    context = {
        'client': client,
        'colis': colis,
        'stats': {
            'total_colis': total_colis,
            'colis_livres': colis_livres,
            'colis_en_transit': colis_en_transit,
        }
    }
    return render(request, 'agent_chine_app/client_detail.html', context)

@agent_chine_required
def client_edit_view(request, client_id):
    """
    Édition d'un client
    """
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            telephone = request.POST.get('telephone')
            first_name = request.POST.get('first_name') or request.POST.get('prenom')
            last_name = request.POST.get('last_name') or request.POST.get('nom')
            email = request.POST.get('email', '')
            adresse = request.POST.get('adresse')
            pays = request.POST.get('pays', 'ML')
            
            # Mettre à jour l'utilisateur
            user = client.user
            user.first_name = first_name
            user.last_name = last_name
            user.telephone = telephone
            user.email = email
            user.save()
            
            # Mettre à jour le profil client
            client.adresse = adresse
            client.pays = pays
            client.save()
            
            messages.success(request, f"✅ Client {user.get_full_name()} mis à jour avec succès.")
            return redirect('agent_chine:client_detail', client_id=client_id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la mise à jour: {str(e)}")
    
    context = {
        'client': client,
        'title': 'Modifier Client',
        'submit_text': 'Mettre à jour',
    }
    return render(request, 'agent_chine_app/client_form.html', context)

@agent_chine_required
def client_delete_view(request, client_id):
    """
    Suppression d'un client
    """
    client = get_object_or_404(Client, id=client_id)
    client.delete()
    messages.success(request, "Client supprimé avec succès.")
    return redirect('agent_chine:client_list')

# === GESTION DES LOTS ===

@agent_chine_required
def lot_list_view(request):
    """
    Liste des lots
    """
    lots = Lot.objects.all().order_by('-date_creation')
    
    # Filtrage par statut
    statut_filter = request.GET.get('statut', '')
    if statut_filter:
        lots = lots.filter(statut=statut_filter)
    
    context = {
        'lots': lots,
        'statut_filter': statut_filter,
        'statut_choices': Lot.STATUS_CHOICES,
    }
    return render(request, 'agent_chine_app/lot_list.html', context)

@agent_chine_required
def lot_create_view(request):
    """
    Création d'un nouveau lot
    """
    if request.method == 'POST':
        try:
            # Créer le lot avec l'agent comme créateur
            lot = Lot.objects.create(
                agent_createur=request.user,
                statut='ouvert'
            )
            
            messages.success(request, f"✅ Lot {lot.numero_lot} créé avec succès.")
            return redirect('agent_chine:lot_detail', lot_id=lot.id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la création du lot: {str(e)}")
    
    context = {
        'title': 'Nouveau Lot',
        'submit_text': 'Créer',
    }
    return render(request, 'agent_chine_app/lot_form.html', context)

@agent_chine_required
def lot_detail_view(request, lot_id):
    """
    Détail d'un lot avec ses colis
    """
    lot = get_object_or_404(Lot, id=lot_id)
    colis = lot.colis.all().order_by('-date_creation')
    
    # Statistiques du lot
    total_colis = colis.count()
    total_poids = sum(float(c.poids) for c in colis)
    total_prix = sum(float(c.prix_calcule) for c in colis)
    
    context = {
        'lot': lot,
        'colis': colis,
        'stats': {
            'total_colis': total_colis,
            'total_poids': total_poids,
            'total_prix': total_prix,
        }
    }
    return render(request, 'agent_chine_app/lot_detail.html', context)

@agent_chine_required
def lot_close_view(request, lot_id):
    """
    Fermer un lot et saisir le prix du transport
    Envoie des notifications aux propriétaires de colis
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    if lot.statut != 'ouvert':
        messages.error(request, "Ce lot ne peut pas être fermé.")
        return redirect('agent_chine:lot_detail', lot_id=lot_id)
    
    # Vérifier que le lot contient des colis
    colis_count = lot.colis.count()
    if colis_count == 0:
        messages.error(request, "❌ Impossible de fermer un lot vide. Ajoutez au moins un colis avant de fermer le lot.")
        return redirect('agent_chine:lot_detail', lot_id=lot_id)
    
    if request.method == 'POST':
        try:
            # Récupérer le prix du transport
            prix_transport = request.POST.get('prix_transport')
            
            if not prix_transport or prix_transport.strip() == '':
                messages.error(request, "❌ Veuillez saisir le prix du transport.")
                raise ValueError("Prix du transport requis")
            
            # Valider que le prix est un nombre positif
            prix_float = float(prix_transport)
            if prix_float <= 0:
                messages.error(request, "❌ Le prix du transport doit être supérieur à zéro.")
                raise ValueError("Prix invalide")
            
            # Fermer le lot
            lot.prix_transport = prix_float
            lot.statut = 'ferme'
            lot.date_fermeture = timezone.now()
            lot.save()
            
            # Les colis restent avec le statut 'receptionne_chine' jusqu'à l'expédition
            # Pas de changement de statut des colis à la fermeture du lot
            
            # Envoyer des notifications de masse aux propriétaires de colis de façon asynchrone
            try:
                from notifications_app.tasks import send_bulk_lot_notifications
                send_bulk_lot_notifications.delay(
                    lot_id=lot.id,
                    notification_type='lot_closed',
                    initiated_by_id=request.user.id
                )
                messages.success(request, f"✅ Lot {lot.numero_lot} fermé avec succès ! Prix transport: {prix_float} CFA. Les notifications sont en cours d'envoi aux {colis_count} clients.")
            except Exception as notif_error:
                messages.success(request, f"✅ Lot {lot.numero_lot} fermé avec succès ! Prix transport: {prix_float} CFA. Erreur lors du lancement des notifications.")
            return redirect('agent_chine:lot_detail', lot_id=lot_id)
                
        except ValueError as ve:
            # Erreurs de validation déjà traitées
            pass
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la fermeture: {str(e)}")
    
    # Calculer les statistiques du lot pour affichage
    colis = lot.colis.all()
    total_poids = sum(float(c.poids) for c in colis)
    total_prix_colis = sum(float(c.prix_calcule) for c in colis)
    
    context = {
        'lot': lot,
        'colis_count': colis_count,
        'total_poids': total_poids,
        'total_prix_colis': total_prix_colis,
        'title': f'Fermer le lot {lot.numero_lot}',
    }
    return render(request, 'agent_chine_app/lot_close.html', context)

@agent_chine_required
def lot_expedite_view(request, lot_id):
    """
    Expédier un lot
    Envoie des notifications d'expédition aux propriétaires de colis
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    if lot.statut != 'ferme':
        messages.error(request, "Ce lot doit être fermé avant d'être expédié.")
        return redirect('agent_chine:lot_detail', lot_id=lot_id)
    
    # Mettre à jour le statut
    lot.statut = 'expedie'
    lot.date_expedition = timezone.now()
    lot.save()
    
    # Mettre à jour le statut des colis
    lot.colis.update(statut='en_transit')
    
    # Envoyer des notifications d'expédition de façon asynchrone
    total_colis = lot.colis.count()
    
    try:
        from notifications_app.tasks import send_bulk_lot_notifications
        send_bulk_lot_notifications.delay(
            lot_id=lot.id,
            notification_type='lot_shipped',
            initiated_by_id=request.user.id
        )
        messages.success(request, f"✅ Lot {lot.numero_lot} expédié avec succès ! Les notifications d'expédition sont en cours d'envoi aux {total_colis} clients.")
    except Exception as notif_error:
        messages.success(request, f"✅ Lot {lot.numero_lot} expédié avec succès ! Erreur lors du lancement des notifications.")
    return redirect('agent_chine:lot_detail', lot_id=lot_id)

# === GESTION DES COLIS ===

@agent_chine_required
def colis_list_view(request):
    """
    Liste de tous les colis
    """
    colis = Colis.objects.all().order_by('-date_creation')
    
    # Filtrage par statut
    statut_filter = request.GET.get('statut', '')
    if statut_filter:
        colis = colis.filter(statut=statut_filter)
    
    context = {
        'colis': colis,
        'statut_filter': statut_filter,
        'statut_choices': Colis.STATUS_CHOICES,
    }
    return render(request, 'agent_chine_app/colis_list.html', context)

@agent_chine_required
def colis_create_view(request, lot_id):
    """
    Création d'un nouveau colis dans un lot
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    if lot.statut != 'ouvert':
        messages.error(request, "Impossible d'ajouter des colis à un lot fermé.")
        return redirect('agent_chine:lot_detail', lot_id=lot_id)
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            client_id = request.POST.get('client')
            type_transport = request.POST.get('type_transport')
            image = request.FILES.get('image')
            longueur = request.POST.get('longueur')
            largeur = request.POST.get('largeur') 
            hauteur = request.POST.get('hauteur')
            poids = request.POST.get('poids')
            mode_paiement = request.POST.get('mode_paiement')
            statut = request.POST.get('statut', 'en_attente')
            description = request.POST.get('description', '')
            
            # Validation des données obligatoires
            if not client_id:
                messages.error(request, "❌ Veuillez sélectionner un client.")
                raise ValueError("Client requis")
            
            if not type_transport:
                messages.error(request, "❌ Veuillez sélectionner un type de transport.")
                raise ValueError("Type de transport requis")
            
            if not image:
                messages.error(request, "❌ Veuillez ajouter une photo du colis.")
                raise ValueError("Photo du colis requise")
            
            # Récupérer le client
            client = get_object_or_404(Client, id=client_id)
            
            # Créer le colis
            colis = Colis.objects.create(
                client=client,
                lot=lot,
                type_transport=type_transport,
                image=image,
                longueur=float(longueur) if longueur else 0,
                largeur=float(largeur) if largeur else 0,
                hauteur=float(hauteur) if hauteur else 0,
                poids=float(poids) if poids else 0,
                mode_paiement=mode_paiement,
                statut=statut,
                description=description
            )
            
            # Envoyer notification WhatsApp de façon asynchrone
            try:
                from notifications_app.tasks import notify_colis_created
                notify_colis_created.delay(colis.id, initiated_by_id=request.user.id)
            except Exception as notif_error:
                # Ne pas faire échouer la création si la notification échoue
                pass
            
            messages.success(request, f"✅ Colis {colis.numero_suivi} créé avec succès pour {client.user.get_full_name()}.")
            return redirect('agent_chine:lot_detail', lot_id=lot_id)
            
        except ValueError as ve:
            # Erreurs de validation déjà traitées
            pass
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la création du colis : {str(e)}")
    
    # Récupérer tous les clients pour la sélection
    clients = Client.objects.all().order_by('user__first_name', 'user__last_name')
    
    context = {
        'lot': lot,
        'clients': clients,
        'title': f'Nouveau Colis - Lot {lot.numero_lot}',
        'submit_text': 'Créer',
    }
    return render(request, 'agent_chine_app/colis_form.html', context)

@agent_chine_required
def colis_detail_view(request, colis_id):
    """
    Détail d'un colis
    """
    colis = get_object_or_404(Colis, id=colis_id)
    
    context = {
        'colis': colis,
    }
    return render(request, 'agent_chine_app/colis_detail.html', context)

@agent_chine_required
def colis_edit_view(request, colis_id):
    """
    Édition d'un colis
    """
    colis = get_object_or_404(Colis, id=colis_id)
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            client_id = request.POST.get('client')
            type_transport = request.POST.get('type_transport')
            image = request.FILES.get('image')  # Nouvelle image (optionnelle)
            longueur = request.POST.get('longueur')
            largeur = request.POST.get('largeur') 
            hauteur = request.POST.get('hauteur')
            poids = request.POST.get('poids')
            mode_paiement = request.POST.get('mode_paiement')
            statut = request.POST.get('statut')
            description = request.POST.get('description', '')
            
            # Validation des données obligatoires
            if not client_id:
                messages.error(request, "❌ Veuillez sélectionner un client.")
                raise ValueError("Client requis")
            
            if not type_transport:
                messages.error(request, "❌ Veuillez sélectionner un type de transport.")
                raise ValueError("Type de transport requis")
            
            # Récupérer le client
            client = get_object_or_404(Client, id=client_id)
            
            # Mettre à jour le colis
            colis.client = client
            colis.type_transport = type_transport
            colis.longueur = float(longueur) if longueur else 0
            colis.largeur = float(largeur) if largeur else 0
            colis.hauteur = float(hauteur) if hauteur else 0
            colis.poids = float(poids) if poids else 0
            colis.mode_paiement = mode_paiement
            colis.statut = statut
            colis.description = description
            
            # Mettre à jour l'image si une nouvelle est fournie
            if image:
                colis.image = image
            
            colis.save()
            
            # Envoyer notification de modification de façon asynchrone
            try:
                from notifications_app.tasks import notify_colis_updated
                notify_colis_updated.delay(colis.id, initiated_by_id=request.user.id)
            except Exception as notif_error:
                # Ne pas faire échouer la modification si la notification échoue
                pass
            
            messages.success(request, f"✅ Colis {colis.numero_suivi} mis à jour avec succès.")
            return redirect('agent_chine:colis_detail', colis_id=colis_id)
            
        except ValueError as ve:
            # Erreurs de validation déjà traitées
            pass
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la modification du colis : {str(e)}")
    
    # Récupérer tous les clients pour la sélection
    clients = Client.objects.all().order_by('user__first_name', 'user__last_name')
    
    context = {
        'colis': colis,
        'clients': clients,
        'title': f'Modifier Colis {colis.numero_suivi}',
        'submit_text': 'Mettre à jour',
    }
    return render(request, 'agent_chine_app/colis_form.html', context)

@agent_chine_required
def colis_delete_view(request, colis_id):
    """
    Suppression d'un colis
    """
    colis = get_object_or_404(Colis, id=colis_id)
    lot_id = colis.lot.id
    colis.delete()
    messages.success(request, "Colis supprimé avec succès.")
    return redirect('agent_chine:lot_detail', lot_id=lot_id)

# === API ===

@agent_chine_required
@require_http_methods(["POST"])
def calculate_price_api(request):
    """
    API pour calculer automatiquement le prix d'un colis avec gestion robuste
    """
    try:
        # Parsing des données JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Données JSON invalides'
            })
        
        # Validation et conversion des paramètres
        try:
            poids = float(data.get('poids', 0))
            longueur = float(data.get('longueur', 0))
            largeur = float(data.get('largeur', 0))
            hauteur = float(data.get('hauteur', 0))
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Paramètres numériques invalides'
            })
        
        pays_destination = data.get('pays_destination', 'ML')
        type_transport = data.get('type_transport', 'cargo')
        
        # Validation des paramètres selon le type de transport
        if type_transport == 'bateau':
            if not all([longueur, largeur, hauteur]):
                return JsonResponse({
                    'success': False,
                    'error': 'Dimensions requises pour transport par bateau',
                    'details': 'Veuillez saisir longueur, largeur et hauteur'
                })
        else:  # cargo ou express
            if not poids:
                return JsonResponse({
                    'success': False,
                    'error': 'Poids requis pour transport cargo/express',
                    'details': 'Veuillez saisir le poids du colis'
                })
        
        # Calculer le volume en m3
        volume_m3 = (longueur * largeur * hauteur) / 1000000
        
        # Vérifier s'il y a des tarifs disponibles
        tarifs_disponibles = ShippingPrice.objects.filter(actif=True)
        total_tarifs = tarifs_disponibles.count()
        
        if total_tarifs == 0:
            # Pas de tarifs configurés - utiliser des tarifs par défaut
            prix_default = calculate_default_price(poids, volume_m3, type_transport)
            
            return JsonResponse({
                'success': True,
                'prix': float(prix_default),
                'volume_m3': volume_m3,
                'message': f'Prix calculé avec tarif par défaut ({type_transport})',
                'debug_info': {
                    'poids': poids,
                    'dimensions': f'{longueur}x{largeur}x{hauteur}cm',
                    'volume_m3': volume_m3,
                    'pays': pays_destination,
                    'type_transport': type_transport,
                    'tarifs_disponibles': 0,
                    'methode': 'tarif_defaut'
                }
            })
        
        # Rechercher les tarifs applicables
        tarifs = ShippingPrice.objects.filter(
            actif=True,
            pays_destination__in=[pays_destination, 'ALL']
        )
        
        prix_max = 0
        tarif_utilise = None
        prix_details = []
        
        # Calculer le prix avec chaque tarif applicable
        for tarif in tarifs:
            try:
                prix_calcule = tarif.calculer_prix(poids, volume_m3)
                prix_details.append({
                    'nom_tarif': tarif.nom_tarif,
                    'methode': tarif.methode_calcul,
                    'prix_calcule': float(prix_calcule)
                })
                
                if prix_calcule > prix_max:
                    prix_max = prix_calcule
                    tarif_utilise = tarif
            except Exception as e:
                # Erreur calcul tarif - continuer avec le tarif suivant
                continue
        
        # Si aucun tarif ne donne de prix, utiliser tarif par défaut
        if prix_max == 0:
            prix_max = calculate_default_price(poids, volume_m3, type_transport)
            methode_utilisee = 'tarif_defaut'
        else:
            methode_utilisee = tarif_utilise.nom_tarif if tarif_utilise else 'inconnu'
        
        return JsonResponse({
            'success': True,
            'prix': float(prix_max),
            'volume_m3': volume_m3,
            'message': f'Prix calculé avec succès ({methode_utilisee})',
            'debug_info': {
                'poids': poids,
                'dimensions': f'{longueur}x{largeur}x{hauteur}cm',
                'volume_m3': volume_m3,
                'pays': pays_destination,
                'type_transport': type_transport,
                'tarifs_disponibles': total_tarifs,
                'tarifs_applicables': len(prix_details),
                'methode': methode_utilisee,
                'prix_details': prix_details
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur serveur: {str(e)}',
            'debug_info': {
                'data_received': str(data) if 'data' in locals() else 'Non disponible'
            }
        })


def calculate_default_price(poids, volume_m3, type_transport):
    """
    Calcule un prix par défaut quand aucun tarif n'est configuré
    """
    # Tarifs par défaut en FCFA
    tarifs_defaut = {
        # Aligné avec Colis.calculer_prix_automatique() (fallback)
        # cargo: 10000 FCFA/kg, express: 12000 FCFA/kg, bateau: 300000 FCFA/m3
        'cargo': 10000,
        'express': 12000,
        'bateau': 300000,
    }
    
    if type_transport == 'bateau':
        return volume_m3 * tarifs_defaut['bateau']
    else:
        return poids * tarifs_defaut.get(type_transport, 10000)

# === AUTRES VUES ===

@agent_chine_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='/auth/login/')
def notifications_view(request):
    """
    Liste des notifications pour l'agent - Accès administrateur uniquement
    """
    notifications = Notification.objects.filter(
        destinataire=request.user
    ).order_by('-date_creation')
    
    context = {
        'notifications': notifications,
    }
    return render(request, 'agent_chine_app/notifications.html', context)

@agent_chine_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='/auth/login/')
def reports_view(request):
    """
    Rapports complets pour l'agent chine avec toutes les statistiques requises
    Affiche les statistiques de parcelles/lots pour Chine et Mali, revenus, stock, etc.
    """
    from datetime import datetime, timedelta
    from django.db.models import Sum, Count, Q, Avg
    from django.utils import timezone
    
    # Date actuelle et périodes
    today = timezone.now().date()
    debut_mois = today.replace(day=1)
    debut_semaine = today - timedelta(days=today.weekday())
    debut_annee = today.replace(month=1, day=1)
    
    # === STATISTIQUES GÉNÉRALES ===
    # Totaux généraux
    total_clients = Client.objects.count()
    total_lots = Lot.objects.count()
    total_colis = Colis.objects.count()
    
    # === STATISTIQUES PAR STATUT - LOTS ===
    lots_ouverts = Lot.objects.filter(statut='ouvert').count()
    lots_fermes = Lot.objects.filter(statut='ferme').count()
    lots_expedies = Lot.objects.filter(statut='expedie').count()
    lots_en_transit = lots_expedies  # Lots expédiés = en transit
    
    # === STATISTIQUES PAR STATUT - COLIS ===
    # Colis selon statut (correspond aux phases du processus)
    colis_en_attente = Colis.objects.filter(statut='en_attente').count()
    colis_recus_chine = Colis.objects.filter(statut='receptionne_chine').count()
    colis_en_transit = Colis.objects.filter(statut='en_transit').count()
    colis_livres_mali = Colis.objects.filter(statut='livre_mali').count() if Colis.objects.filter(statut='livre_mali').exists() else 0
    
    # === STOCK ET VALEURS ===
    # Stock de colis enregistrés en Chine avec valeur totale
    stock_colis_chine = Colis.objects.filter(
        statut__in=['en_attente', 'receptionne_chine']
    )
    stock_total_chine = stock_colis_chine.count()
    valeur_totale_stock_chine = sum(float(colis.prix_calcule or 0) for colis in stock_colis_chine)
    
    # Stock total des colis livrés et en entrepôt Mali
    stock_colis_mali = Colis.objects.filter(
        statut__in=['en_transit', 'livre_mali']
    )
    stock_total_mali = stock_colis_mali.count()
    
    # === PRIX ET REVENUS ===
    # Prix total estimé des lots (prix de transport)
    lots_avec_prix = Lot.objects.filter(prix_transport__isnull=False)
    prix_total_lots = sum(float(lot.prix_transport or 0) for lot in lots_avec_prix)
    
    # Revenus du mois courant
    lots_facturable_mois = Lot.objects.filter(
        statut__in=['ferme', 'expedie'],
        date_fermeture__gte=debut_mois
    )
    revenus_mois = sum(float(lot.prix_transport or 0) for lot in lots_facturable_mois)
    
    # Revenus totaux
    lots_facturable_total = Lot.objects.filter(statut__in=['ferme', 'expedie'])
    revenus_totaux = sum(float(lot.prix_transport or 0) for lot in lots_facturable_total)
    
    # === STATISTIQUES JOURNALIÈRES ===
    # Colis livrés aujourd'hui (estimation)
    colis_livres_aujourd_hui = Colis.objects.filter(
        date_modification__date=today
    ).count() if Colis.objects.filter(date_modification__date=today).exists() else 0
    
    # Montant journalier des colis livrés
    colis_jour = Colis.objects.filter(date_creation__date=today)
    montant_journalier = sum(float(colis.prix_calcule or 0) for colis in colis_jour)
    
    # === STATISTIQUES TEMPORELLES ===
    # Cette semaine
    colis_semaine = Colis.objects.filter(date_creation__date__gte=debut_semaine).count()
    lots_semaine = Lot.objects.filter(date_creation__date__gte=debut_semaine).count()
    
    # Ce mois
    colis_mois = Colis.objects.filter(date_creation__date__gte=debut_mois).count()
    lots_mois = Lot.objects.filter(date_creation__date__gte=debut_mois).count()
    clients_mois = Client.objects.filter(date_creation__date__gte=debut_mois).count()
    
    # Cette année
    colis_annee = Colis.objects.filter(date_creation__date__gte=debut_annee).count()
    lots_annee = Lot.objects.filter(date_creation__date__gte=debut_annee).count()
    
    # === TYPES DE TRANSPORT ===
    colis_par_transport = {
        'cargo': Colis.objects.filter(type_transport='cargo').count(),
        'express': Colis.objects.filter(type_transport='express').count(),
        'bateau': Colis.objects.filter(type_transport='bateau').count(),
    }
    
    # === CROISSANCE ET TENDANCES ===
    # Croissance mensuelle (vs mois précédent)
    mois_precedent = (debut_mois - timedelta(days=1)).replace(day=1)
    fin_mois_precedent = debut_mois - timedelta(days=1)
    
    colis_mois_precedent = Colis.objects.filter(
        date_creation__date__gte=mois_precedent,
        date_creation__date__lte=fin_mois_precedent
    ).count()
    
    if colis_mois_precedent > 0:
        croissance_colis = ((colis_mois - colis_mois_precedent) / colis_mois_precedent) * 100
    else:
        croissance_colis = 100 if colis_mois > 0 else 0
    
    # === ACTIVITÉ RÉCENTE ===
    derniers_lots = Lot.objects.select_related().prefetch_related('colis').order_by('-date_creation')[:10]
    derniers_colis = Colis.objects.select_related('client__user', 'lot').order_by('-date_creation')[:10]
    
    # === PERFORMANCES MOYENNES ===
    poids_moyen = Colis.objects.aggregate(avg_poids=Avg('poids'))['avg_poids'] or 0
    prix_moyen = Colis.objects.aggregate(avg_prix=Avg('prix_calcule'))['avg_prix'] or 0
    
    # === ALERTES ET MONITORING ===
    # Lots ouverts depuis plus de 7 jours
    date_limite_lot = today - timedelta(days=7)
    lots_anciens = Lot.objects.filter(
        statut='ouvert',
        date_creation__date__lt=date_limite_lot
    ).count()
    
    # Colis en attente depuis plus de 3 jours
    date_limite_colis = today - timedelta(days=3)
    colis_en_retard = Colis.objects.filter(
        statut='en_attente',
        date_creation__date__lt=date_limite_colis
    ).count()
    
    context = {
        'title': 'Rapports & Analyses',
        
        # Statistiques générales
        'stats_generales': {
            'total_clients': total_clients,
            'total_lots': total_lots,
            'total_colis': total_colis,
        },
        
        # Statut des lots
        'stats_lots': {
            'ouverts': lots_ouverts,
            'fermes': lots_fermes,
            'expedies': lots_expedies,
            'en_transit': lots_en_transit,
        },
        
        # Statut des colis (Chine et Mali)
        'stats_colis': {
            'en_attente': colis_en_attente,
            'recus_chine': colis_recus_chine,
            'en_transit': colis_en_transit,
            'livres_mali': colis_livres_mali,
        },
        
        # Stock et valeurs
        'stock_chine': {
            'total_colis': stock_total_chine,
            'valeur_totale': valeur_totale_stock_chine,
        },
        
        'stock_mali': {
            'total_colis': stock_total_mali,
        },
        
        # Revenus et prix
        'finances': {
            'prix_total_lots': prix_total_lots,
            'revenus_mois': revenus_mois,
            'revenus_totaux': revenus_totaux,
            'montant_journalier': montant_journalier,
        },
        
        # Statistiques journalières
        'stats_journalieres': {
            'colis_livres': colis_livres_aujourd_hui,
            'montant': montant_journalier,
        },
        
        # Statistiques temporelles
        'stats_temporelles': {
            'semaine': {
                'colis': colis_semaine,
                'lots': lots_semaine,
            },
            'mois': {
                'colis': colis_mois,
                'lots': lots_mois,
                'clients': clients_mois,
            },
            'annee': {
                'colis': colis_annee,
                'lots': lots_annee,
            },
        },
        
        # Types de transport
        'colis_par_transport': colis_par_transport,
        
        # Croissance et performances
        'performances': {
            'croissance_colis': croissance_colis,
            'poids_moyen': poids_moyen,
            'prix_moyen': prix_moyen,
        },
        
        # Alertes
        'alertes': {
            'lots_anciens': lots_anciens,
            'colis_en_retard': colis_en_retard,
        },
        
        # Activité récente
        'derniers_lots': derniers_lots,
        'derniers_colis': derniers_colis,
        
        # Dates
        'dates': {
            'aujourd_hui': today,
            'debut_mois': debut_mois,
            'debut_semaine': debut_semaine,
        },
    }
    
    return render(request, 'agent_chine_app/reports.html', context)

# === GESTION AUTOMATIQUE DES COMPTES CLIENTS ===

@agent_chine_required
@require_http_methods(["POST"])
def create_client_account_api(request):
    """
    API pour créer automatiquement un compte client lors de la création d'un colis
    """
    try:
        data = json.loads(request.body)
        
        # Validation des données requises
        required_fields = ['telephone', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False, 
                    'error': f'Le champ {field} est requis'
                })
        
        # Créer ou récupérer le client
        result = ClientAccountManager.get_or_create_client(
            telephone=data['telephone'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email'),
            notify=data.get('notify', True)
        )
        
        response_data = {
            'success': True,
            'created': result['created'],
            'client_id': result['client'].id,
            'client_name': result['client'].get_full_name(),
            'client_telephone': result['client'].telephone,
            'notification_sent': result['notification_sent'],
        }
        
        # Inclure le mot de passe seulement si c'est un nouveau compte
        if result['created'] and result['password']:
            response_data['temp_password'] = result['password']
            response_data['message'] = f'Nouveau compte créé pour {result["client"].get_full_name()}. Identifiants envoyés par WhatsApp.'
        else:
            response_data['message'] = f'Client existant: {result["client"].get_full_name()}'
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Données JSON invalides'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@agent_chine_required
@require_http_methods(["POST"])
def resend_client_credentials_api(request, client_id):
    """
    API pour renvoyer les identifiants à un client existant
    """
    try:
        client = get_object_or_404(User, id=client_id, role='client')
        result = send_client_credentials(client.telephone)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': f'Nouveaux identifiants envoyés à {client.get_full_name()}',
                'notification_sent': result['notification_sent']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Erreur inconnue')
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@agent_chine_required
def user_clients_list(request):
    """
    Liste tous les comptes utilisateurs clients (pour debug/admin)
    """
    users_clients = User.objects.filter(role='client').order_by('-date_joined')
    
    # Recherche
    search_query = request.GET.get('search', '')
    if search_query:
        users_clients = users_clients.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(telephone__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'users_clients': users_clients,
        'search_query': search_query,
        'total_users': users_clients.count()
    }
    
    return render(request, 'agent_chine_app/user_clients_list.html', context)

@agent_chine_required
def check_client_exists_api(request):
    """
    API pour vérifier si un client existe déjà par numéro de téléphone
    """
    telephone = request.GET.get('telephone')
    if not telephone:
        return JsonResponse({'error': 'Numéro de téléphone requis'})
    
    try:
        # Nettoyer le numéro
        clean_phone = ClientAccountManager._clean_phone_number(telephone)
        
        # Chercher l'utilisateur
        user = User.objects.filter(telephone=clean_phone, role='client').first()
        
        if user:
            return JsonResponse({
                'exists': True,
                'client': {
                    'id': user.id,
                    'name': user.get_full_name(),
                    'telephone': user.telephone,
                    'email': user.email,
                    'date_joined': user.date_joined.isoformat()
                }
            })
        else:
            return JsonResponse({'exists': False})
            
    except Exception as e:
        return JsonResponse({'error': str(e)})

@agent_chine_required
def client_info_api(request, client_id):
    """
    API pour récupérer les informations d'un client pour l'autocomplétion
    """
    try:
        client = get_object_or_404(Client, id=client_id)
        
        return JsonResponse({
            'success': True,
            'client': {
                'id': client.id,
                'name': client.user.get_full_name(),
                'first_name': client.user.first_name,
                'last_name': client.user.last_name,
                'telephone': client.user.telephone,
                'email': client.user.email or '',
                'adresse': client.adresse,
                'pays': client.pays,
                'pays_display': client.get_pays_display(),
                'date_creation': client.date_creation.isoformat()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@agent_chine_required
def clients_search_api(request):
    """
    API de recherche clients pour Select2 avec pagination
    Optimisée pour les grandes bases de données client
    """
    try:
        # Paramètres de recherche
        search_term = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))
        per_page = 20  # Nombre de résultats par page
        
        # Base query
        clients = Client.objects.select_related('user').order_by('user__first_name', 'user__last_name')
        
        # Filtrer par terme de recherche si fourni
        if search_term:
            clients = clients.filter(
                Q(user__first_name__icontains=search_term) |
                Q(user__last_name__icontains=search_term) |
                Q(user__telephone__icontains=search_term) |
                Q(pays__icontains=search_term) |
                Q(user__email__icontains=search_term)
            )
        
        # Pagination
        total_count = clients.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        clients_page = clients[start_index:end_index]
        
        # Formatter les résultats pour Select2
        results = []
        for client in clients_page:
            results.append({
                'id': client.id,
                'text': f"{client.user.get_full_name()} - {client.user.telephone} ({client.get_pays_display()})",
                'name': client.user.get_full_name(),
                'telephone': client.user.telephone,
                'email': client.user.email or '',
                'pays': client.pays,
                'pays_display': client.get_pays_display(),
                'adresse': client.adresse_complete,
            })
        
        # Réponse Select2 format
        response_data = {
            'results': results,
            'pagination': {
                'more': end_index < total_count  # Y a-t-il plus de résultats ?
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'results': [],
            'error': str(e)
        })

@agent_chine_required
def wachap_monitoring_view(request):
    """
    Vue de monitoring des instances WaChap
    """
    from notifications_app.wachap_monitoring import (
        wachap_monitor, get_wachap_monitoring_status, get_wachap_alert_history
    )
    from django.utils import timezone
    
    # Récupérer le statut actuel
    current_status = get_wachap_monitoring_status()
    
    # Récupérer l'historique des alertes
    alert_history = get_wachap_alert_history()
    
    # Exécuter une vérification temps réel si demandé
    if request.GET.get('check') == 'now':
        current_status = wachap_monitor.run_monitoring_check()
        # Convertir en format attendu
        current_status = {
            'timestamp': timezone.now().isoformat(),
            'connected_count': sum(1 for s in current_status.values() if s.get('connected')),
            'total_instances': len(current_status),
            'disconnected_instances': [r for r, s in current_status.items() if not s.get('connected')],
            'all_status': current_status
        }
    
    context = {
        'current_status': current_status,
        'alert_history': alert_history[-10:],  # 10 dernières alertes
        'page_title': 'Monitoring WaChap',
    }
    
    return render(request, 'agent_chine_app/wachap_monitoring.html', context)
