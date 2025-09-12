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
import json

from .models import CustomUser, PasswordResetToken
from .forms import LoginForm, RegistrationForm, PasswordResetRequestForm, PasswordResetForm, AdminChinaLoginForm


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
        print(f"\n=== DEBUG LOGIN ===")
        print(f"POST data: {request.POST}")
        print(f"Form valid: {form.is_valid()}")
        print(f"Form errors: {form.errors}")
        print(f"Form non-field errors: {form.non_field_errors()}")
        print(f"Form cleaned_data: {getattr(form, 'cleaned_data', 'No cleaned_data')}")
        if form.is_valid():
            # Le formulaire a déjà vérifié le téléphone + mot de passe avec authenticate()
            telephone = form.cleaned_data['phone_number']
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            
            # Générer et stocker l'OTP
            otp_code = generate_otp_code()
            print(f"OTP generated: {otp_code}")
            cache_key = f"otp_{telephone}"
            cache.set(cache_key, {
                'code': otp_code,
                'user_id': user.id,
                'timestamp': timezone.now().isoformat()
            }, timeout=600)  # 10 minutes
            
            # Envoyer l'OTP via WaChap
            success, message = send_whatsapp_otp(telephone, otp_code)
            print(f"OTP WaChap sent: {success}, {message}")
            
            if success:
                # Stocker le téléphone en session pour la vérification OTP
                request.session['otp_telephone'] = telephone
                request.session['pre_authenticated_user_id'] = user.id
                messages.success(request, f"Identifiants validés ! {message}")
                print(f"OTP sent: {success}, {message}")
                return redirect('authentication:verify_otp')
            else:
                messages.error(request, f"Erreur d'envoi du code: {message}")
                print(f"OTP sent: {success}, {message}")
                
    else:
        form = LoginForm()
        print(f"Form valid: {form.is_valid()}")
    
    return render(request, 'authentication/login.html', {'form': form})

def verify_otp_view(request):
    """Vue de vérification du code OTP"""
    telephone = request.session.get('otp_telephone')
    if not telephone:
        messages.error(request, "Session expirée. Veuillez vous reconnecter.")
        return redirect('authentication:login')
    
    # Récupérer l'OTP depuis le cache pour l'afficher (mode test)
    cache_key = f"otp_{telephone}"
    otp_data = cache.get(cache_key)
    current_otp = otp_data.get('code') if otp_data else None
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code')
        
        if otp_data and entered_otp == otp_data['code']:
            # OTP valide, connecter l'utilisateur
            try:
                user = CustomUser.objects.get(id=otp_data['user_id'])
                login(request, user)
                
                # Nettoyer la session et le cache
                del request.session['otp_telephone']
                cache.delete(cache_key)
                
                messages.success(request, f"Connexion réussie. Bienvenue {user.get_full_name()}!")
                return redirect(get_dashboard_url_by_role(user))
                
            except CustomUser.DoesNotExist:
                messages.error(request, "Erreur de connexion. Utilisateur introuvable.")
        else:
            messages.error(request, "Code OTP invalide ou expiré.")
    
    return render(request, 'authentication/verify_otp.html', {
        'telephone': telephone,
        'current_otp': current_otp  # Pour affichage en mode test
    })

def role_based_login_view(request, role):
    """Vue de connexion spécifique à un rôle"""
    valid_roles = ['client', 'agent_chine', 'agent_mali', 'admin', 'admin_mali']
    if role not in valid_roles:
        messages.error(request, "Rôle invalide.")
        return redirect('authentication:login')
    
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        print(f"\n=== DEBUG LOGIN {role.upper()} ===")
        print(f"POST data: {request.POST}")
        
        # Vérifier le token CSRF avant de traiter le formulaire
        try:
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
        except Exception as e:
            print(f"CSRF check error: {e}")
        
        form = LoginForm(request.POST, request=request)
        print(f"Form valid: {form.is_valid()}")
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
        
        if form.is_valid():
            # Le formulaire a déjà vérifié téléphone + mot de passe avec authenticate()
            telephone = form.cleaned_data['phone_number']
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            print(f"User authenticated: {user}")
            print(f"User role: {user.role if user else 'None'}")
            
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
            
            # Générer et envoyer l'OTP
            otp_code = generate_otp_code()
            cache_key = f"otp_{telephone}"
            cache.set(cache_key, {
                'code': otp_code,
                'user_id': user.id,
                'role': role,
                'timestamp': timezone.now().isoformat()
            }, timeout=600)
            
            # Envoyer l'OTP via WaChap
            success, message = send_whatsapp_otp(telephone, otp_code)
            
            if success:
                request.session['otp_telephone'] = telephone
                request.session['login_role'] = role
                request.session['pre_authenticated_user_id'] = user.id
                messages.success(request, f"Identifiants validés ! {message}")
                return redirect('authentication:verify_otp')
            else:
                messages.error(request, f"Erreur d'envoi du code: {message}")
                
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

def register_view(request):
    """Vue d'inscription (si activée)"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Compte créé avec succès pour {user.telephone}!")
            return redirect('authentication:login')
    else:
        form = RegistrationForm()
    
    return render(request, 'authentication/register.html', {'form': form})

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
    
    return render(request, 'authentication/password_reset_verify.html', {
        'telephone': telephone,
        'current_otp': current_otp
    })

def password_reset_confirm_view(request):
    """Vue de confirmation de nouveau mot de passe"""
    telephone = request.session.get('reset_telephone')
    verified = request.session.get('reset_verified')
    
    if not telephone or not verified:
        messages.error(request, "Session invalide. Veuillez recommencer.")
        return redirect('authentication:password_reset_request')
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            
            try:
                user = CustomUser.objects.get(telephone=telephone)
                user.set_password(new_password)
                user.save()
                
                # Nettoyer la session
                del request.session['reset_telephone']
                del request.session['reset_verified']
                cache.delete(f"reset_otp_{telephone}")
                
                messages.success(request, "Mot de passe réinitialisé avec succès!")
                return redirect('authentication:login')
                
            except CustomUser.DoesNotExist:
                messages.error(request, "Erreur lors de la réinitialisation.")
                
    else:
        form = PasswordResetForm()
    
    return render(request, 'authentication/password_reset_confirm.html', {
        'form': form,
        'telephone': telephone
    })

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

def admin_chine_login_view(request):
    """Vue de connexion spécifique pour Admin Chine avec gestion des numéros chinois"""
    if request.user.is_authenticated and request.user.is_admin_chine:
        return redirect('admin_chine_app:dashboard')
    
    if request.method == 'POST':
        form = AdminChinaLoginForm(request.POST, request=request)
        
        if form.is_valid():
            telephone = form.cleaned_data['phone_number']
            user = form.user_cache
            
            # Générer et envoyer l'OTP
            otp_code = generate_otp_code()
            cache_key = f"otp_{telephone}"
            cache.set(cache_key, {
                'code': otp_code,
                'user_id': user.id,
                'role': 'admin_chine',
                'timestamp': timezone.now().isoformat()
            }, timeout=600)
            
            # Envoyer l'OTP via WaChap
            success, message = send_whatsapp_otp(telephone, otp_code)
            
            if success:
                request.session['otp_telephone'] = telephone
                request.session['login_role'] = 'admin_chine'
                request.session['pre_authenticated_user_id'] = user.id
                messages.success(request, f"Identifiants validés ! {message}")
                return redirect('authentication:verify_otp')
            else:
                messages.error(request, f"Erreur d'envoi du code: {message}")
    else:
        form = AdminChinaLoginForm()
    
    return render(request, 'authentication/login_admin_chine.html', {
        'form': form,
        'role': 'admin_chine',
        'role_display': 'Administrateur Chine'
    })


def home_view(request):
    """Page d'accueil avec liens de connexion par rôle"""
    return render(request, 'authentication/home.html')
