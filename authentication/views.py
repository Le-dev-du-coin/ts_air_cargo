import random
import string
from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.cache import cache
from notifications_app.wachap_service import send_whatsapp_otp
from .otp_service import AsyncOTPService, get_user_friendly_message
import json

from .models import CustomUser, PasswordResetToken
from .forms import LoginForm, PasswordResetRequestForm, PasswordResetForm


def generate_otp_code():
    """Génère un code OTP aléatoire de 6 chiffres"""
    return ''.join(random.choices(string.digits, k=6))


def get_dashboard_url_by_role(user):
    """Retourne l'URL du dashboard selon le rôle de l'utilisateur"""
    if user.is_superuser or user.role == 'superuser':
        return '/admin/'
    elif user.role == 'agent_chine':
        return reverse('agent_chine:dashboard')
    elif user.role == 'agent_mali':
        return reverse('agent_mali:dashboard')
    elif user.role == 'admin_chine' or user.is_admin_chine:
        return reverse('admin_chine_app:dashboard')
    elif user.role == 'admin_mali' or user.is_admin_mali:
        return reverse('admin_mali_app:dashboard')
    elif user.role == 'client':
        return reverse('client_app:dashboard')
    else:
        return reverse('authentication:home')  # Fallback

def login_view(request):
    """Vue de connexion générale avec authentification téléphone + mot de passe puis OTP"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            # Le formulaire a déjà vérifié le téléphone + mot de passe avec authenticate()
            telephone = form.cleaned_data['phone_number']
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            
            # Envoyer l'OTP de manière asynchrone
            otp_result = AsyncOTPService.send_otp_async(
                phone_number=telephone,
                user_id=user.id,
                extra_data={'timestamp': timezone.now().isoformat()}
            )
            
            if otp_result['success']:
                # Stocker les informations de session
                request.session['otp_cache_key'] = otp_result['cache_key']
                request.session['otp_telephone'] = telephone
                request.session['pre_authenticated_user_id'] = user.id
                messages.success(request, f"Identifiants validés ! {otp_result['user_message']}")
                return redirect('authentication:verify_otp')
            else:
                user_message = get_user_friendly_message(otp_result.get('error', 'Erreur inconnue'))
                messages.error(request, f"Problème d'envoi du code: {user_message}")
                
    else:
        form = LoginForm()
    
    return render(request, 'authentication/login.html', {'form': form})

def verify_otp_view(request):
    """Vue de vérification du code OTP avec support asynchrone"""
    # Si déjà authentifié, rediriger vers le dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))

    telephone = request.session.get('otp_telephone')
    cache_key = request.session.get('otp_cache_key')
    
    if not telephone or not cache_key:
        messages.error(request, "Session expirée. Veuillez vous reconnecter.")
        return redirect('authentication:home')
    
    # Récupérer le statut actuel de l'OTP
    otp_status = AsyncOTPService.get_otp_status(cache_key)
    
    if not otp_status['found']:
        messages.error(request, otp_status['user_message'])
        return redirect('authentication:home')
    
    # Variables pour le template
    current_otp = otp_status.get('code') if settings.DEBUG else None
    sending_status = otp_status.get('status', 'pending')
    user_message = otp_status.get('user_message', '')
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code')
        
        # Vérifier le code OTP
        verification_result = AsyncOTPService.verify_otp(cache_key, entered_otp)
        
        if verification_result['success']:
            # OTP valide, connecter l'utilisateur
            try:
                user = CustomUser.objects.get(id=verification_result['user_id'])
                login(request, user)
                
                # Nettoyer la session
                request.session.pop('otp_telephone', None)
                request.session.pop('otp_cache_key', None)
                request.session.pop('pre_authenticated_user_id', None)
                
                messages.success(request, f"Connexion réussie. Bienvenue {user.get_full_name()}!")
                return redirect(get_dashboard_url_by_role(user))
                
            except CustomUser.DoesNotExist:
                messages.error(request, "Erreur de connexion. Utilisateur introuvable.")
        else:
            messages.error(request, verification_result['user_message'])
    
    # Empêcher la mise en cache de la page OTP
    response = render(request, 'authentication/verify_otp.html', {
        'telephone': telephone,
        'current_otp': current_otp,  # Pour affichage en mode test
        'sending_status': sending_status,
        'status_message': user_message,
        'cache_key': cache_key  # Pour le polling AJAX
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@csrf_exempt
def otp_status_ajax(request):
    """Vue AJAX pour vérifier le statut d'envoi de l'OTP"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    cache_key = request.POST.get('cache_key')
    if not cache_key:
        return JsonResponse({'error': 'Clé cache manquante'}, status=400)
    
    # Vérifier que la clé appartient à la session actuelle
    session_cache_key = request.session.get('otp_cache_key')
    if cache_key != session_cache_key:
        return JsonResponse({'error': 'Clé cache non valide'}, status=400)
    
    # Récupérer le statut
    otp_status = AsyncOTPService.get_otp_status(cache_key)
    
    if not otp_status['found']:
        return JsonResponse({
            'found': False,
            'expired': True,
            'user_message': otp_status['user_message']
        })
    
    return JsonResponse({
        'found': True,
        'expired': False,
        'status': otp_status.get('status', 'pending'),
        'user_message': otp_status.get('user_message', ''),
        'attempts': otp_status.get('attempts', 0),
        'show_code': settings.DEBUG,
        'code': otp_status.get('code') if settings.DEBUG else None
    })

def role_based_login_view(request, role):
    """Vue de connexion spécifique à un rôle"""
    valid_roles = ['client', 'agent_chine', 'agent_mali', 'admin', 'admin_mali']
    if role not in valid_roles:
        messages.error(request, "Rôle invalide.")
        return redirect('authentication:home')
    
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        
        # Vérifier le token CSRF avant de traiter le formulaire
        from django.middleware.csrf import get_token
        csrf_token = request.POST.get('csrfmiddlewaretoken')
        if not csrf_token:
            messages.error(request, "Erreur de sécurité: Token CSRF manquant.")
            return render(request, f'authentication/login_{role}.html', {
                'form': LoginForm(),
                'role': role,
                'role_display': {
                    'client': 'Client',
                    'agent_chine': 'Agent Chine',
                    'agent_mali': 'Agent Mali',
                    'admin': 'Administrateur',
                    'admin_mali': 'Admin Mali'
                }.get(role, role.title())
            })
        
        form = LoginForm(request.POST, request=request)
        
        if form.is_valid():
            # Le formulaire a déjà vérifié téléphone + mot de passe avec authenticate()
            telephone = form.cleaned_data['phone_number']
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            
            # Vérifier que l'utilisateur a le bon rôle
            if role == 'admin' and not (user.is_admin_chine or user.is_admin_mali):
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm()})
            elif role == 'admin_mali' and not user.is_admin_mali:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm()})
            elif role == 'agent_chine' and not user.is_agent_chine:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm()})
            elif role == 'agent_mali' and not user.is_agent_mali:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm()})
            elif role == 'client' and not user.is_client:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm()})
            
            # Générer et envoyer l'OTP de manière asynchrone (aligné avec verify_otp_view)
            otp_result = AsyncOTPService.send_otp_async(
                phone_number=telephone,
                user_id=user.id,
                extra_data={'role': role, 'timestamp': timezone.now().isoformat()}
            )

            if otp_result['success']:
                # Stocker les mêmes clés de session que verify_otp_view attend
                request.session['otp_cache_key'] = otp_result['cache_key']
                request.session['otp_telephone'] = telephone
                request.session['pre_authenticated_user_id'] = user.id
                request.session['login_role'] = role
                messages.success(request, f"Identifiants validés ! {otp_result['user_message']}")
                return redirect('authentication:verify_otp')
            else:
                user_message = get_user_friendly_message(otp_result.get('error', 'Erreur inconnue'))
                messages.error(request, f"Problème d'envoi du code: {user_message}")
                
    else:
        form = LoginForm()
    
    return render(request, f'authentication/login_{role}.html', {
        'form': form,
        'role': role,
        'role_display': {
            'client': 'Client',
            'agent_chine': 'Agent Chine',
            'agent_mali': 'Agent Mali',
            'admin': 'Administrateur',
            'admin_mali': 'Admin Mali'
        }.get(role, role.title())
    })

@login_required
def logout_view(request):
    """Vue de déconnexion"""
    user_name = request.user.get_full_name()
    logout(request)
    messages.success(request, f"Au revoir {user_name}! Vous êtes maintenant déconnecté.")
    return redirect('authentication:home')

# register_view supprimée pour la production

def password_reset_request_view(request):
    """Vue de demande de réinitialisation de mot de passe"""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            telephone = form.cleaned_data['phone_number']
            
            try:
                user = CustomUser.objects.get(telephone=telephone)
                
                # Générer un code OTP pour la réinitialisation
                otp_code = generate_otp_code()
                cache_key = f"reset_otp_{telephone}"
                cache.set(cache_key, {
                    'code': otp_code,
                    'user_id': user.id,
                    'timestamp': timezone.now().isoformat()
                }, timeout=600)
                
                # Envoyer l'OTP via WaChap
                success, message = send_whatsapp_otp(telephone, otp_code)
                
                if success:
                    request.session['reset_telephone'] = telephone
                    messages.success(request, f"Code de réinitialisation envoyé. {message}")
                    return redirect('authentication:password_reset_verify')
                else:
                    messages.error(request, f"Erreur d'envoi: {message}")
                    
            except CustomUser.DoesNotExist:
                # Pour la sécurité, ne pas révéler si le compte existe ou non
                messages.info(request, "Si ce numéro existe, un code de réinitialisation a été envoyé.")
                
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'authentication/password_reset_request.html', {'form': form})

def password_reset_verify_view(request):
    """Vue de vérification OTP pour réinitialisation de mot de passe"""
    # Si déjà authentifié, rediriger vers le dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))

    telephone = request.session.get('reset_telephone')
    if not telephone:
        messages.error(request, "Session expirée. Veuillez recommencer.")
        return redirect('authentication:password_reset_request')
    
    cache_key = f"reset_otp_{telephone}"
    otp_data = cache.get(cache_key)
    current_otp = otp_data.get('code') if otp_data else None
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code')
        
        if otp_data and entered_otp == otp_data['code']:
            # OTP valide, rediriger vers la réinitialisation
            request.session['reset_verified'] = True
            return redirect('authentication:password_reset_confirm')
        else:
            messages.error(request, "Code OTP invalide ou expiré.")
    
    # Empêcher la mise en cache
    response = render(request, 'authentication/password_reset_verify.html', {
        'telephone': telephone,
        'current_otp': current_otp
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def password_reset_confirm_view(request):
    """Vue de confirmation de nouveau mot de passe"""
    telephone = request.session.get('reset_telephone')
    verified = request.session.get('reset_verified')
    
    if not telephone or not verified:
        messages.error(request, "Session invalide. Veuillez recommencer.")
        return redirect('authentication:password_reset_request')
    
    if request.method == 'POST':
        # Récupérer les champs tels qu'envoyés par le template (new_password1/new_password2)
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        # Validations de base
        if not new_password1 or not new_password2:
            messages.error(request, "Veuillez saisir et confirmer le nouveau mot de passe.")
        elif new_password1 != new_password2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        elif len(new_password1) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        else:
            try:
                user = CustomUser.objects.get(telephone=telephone)
                user.set_password(new_password1)
                user.save()

                # Nettoyer la session
                del request.session['reset_telephone']
                del request.session['reset_verified']
                cache.delete(f"reset_otp_{telephone}")

                messages.success(request, "Mot de passe réinitialisé avec succès!")
                return redirect('authentication:home')

            except CustomUser.DoesNotExist:
                messages.error(request, "Erreur lors de la réinitialisation.")
    
    # Afficher la page de confirmation (le template gère les champs)
    response = render(request, 'authentication/password_reset_confirm.html', {
        'telephone': telephone
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@csrf_exempt
@require_http_methods(["POST"])
def resend_otp_view(request):
    """API pour renvoyer un code OTP"""
    telephone = request.session.get('otp_telephone') or request.session.get('reset_telephone')
    
    if not telephone:
        return JsonResponse({'success': False, 'message': 'Session expirée'})
    
    # Vérifier le délai entre les envois (protection contre le spam)
    last_sent_key = f"last_otp_sent_{telephone}"
    last_sent = cache.get(last_sent_key)
    
    if last_sent:
        time_diff = timezone.now() - timezone.fromisoformat(last_sent)
        if time_diff < timedelta(minutes=1):
            return JsonResponse({
                'success': False, 
                'message': 'Veuillez attendre 1 minute avant de renvoyer un code'
            })
    
    try:
        user = CustomUser.objects.get(telephone=telephone)
        otp_code = generate_otp_code()
        
        # Déterminer le type d'OTP (connexion ou réinitialisation)
        if request.session.get('reset_telephone'):
            cache_key = f"reset_otp_{telephone}"
        else:
            cache_key = f"otp_{telephone}"
        
        cache.set(cache_key, {
            'code': otp_code,
            'user_id': user.id,
            'timestamp': timezone.now().isoformat()
        }, timeout=600)
        
        # Envoyer l'OTP via WaChap
        success, message = send_whatsapp_otp(telephone, otp_code)
        
        if success:
            # Enregistrer l'heure d'envoi
            cache.set(last_sent_key, timezone.now().isoformat(), timeout=60)
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message})
            
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Utilisateur introuvable'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Erreur: {str(e)}'})

## Vue admin_chine_login_view supprimée: l'admin passe par login_admin (role_based_login_view) et est redirigé selon son rôle


def home_view(request):
    """Page d'accueil avec liens de connexion par rôle"""
    # Si l'utilisateur est déjà connecté, le rediriger vers son dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    return render(request, 'authentication/home.html')
