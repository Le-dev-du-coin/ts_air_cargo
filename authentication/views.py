from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from .models import CustomUser
from .forms import LoginForm


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
    """Vue de connexion générale avec authentification directe téléphone + mot de passe"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            
            # Connecter directement l'utilisateur
            login(request, user)
            messages.success(request, f"Connexion réussie. Bienvenue {user.get_full_name()}!")
            return redirect(get_dashboard_url_by_role(user))
                
    else:
        form = LoginForm()
    
    return render(request, 'authentication/login.html', {'form': form})


def role_based_login_view(request, role):
    """Vue de connexion spécifique à un rôle avec authentification directe"""
    valid_roles = ['client', 'agent_chine', 'agent_mali', 'admin', 'admin_mali']
    if role not in valid_roles:
        messages.error(request, "Rôle invalide.")
        return redirect('authentication:home')
    
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        form = LoginForm(request.POST, request=request)
        
        if form.is_valid():
            user = form.user_cache  # L'utilisateur authentifié depuis le formulaire
            
            # Vérifier que l'utilisateur a le bon rôle
            if role == 'admin' and not (user.is_admin_chine or user.is_admin_mali):
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm(), 'role': role})
            elif role == 'admin_mali' and not user.is_admin_mali:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm(), 'role': role})
            elif role == 'agent_chine' and not user.is_agent_chine:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm(), 'role': role})
            elif role == 'agent_mali' and not user.is_agent_mali:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm(), 'role': role})
            elif role == 'client' and not user.is_client:
                messages.error(request, "Accès non autorisé pour ce rôle.")
                return render(request, f'authentication/login_{role}.html', {'form': LoginForm(), 'role': role})
            
            # Connecter directement l'utilisateur
            login(request, user)
            messages.success(request, f"Connexion réussie. Bienvenue {user.get_full_name()}!")
            return redirect(get_dashboard_url_by_role(user))
                
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

def home_view(request):
    """Page d'accueil avec liens de connexion par rôle"""
    # Si l'utilisateur est déjà connecté, le rediriger vers son dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    return render(request, 'authentication/home.html')


def password_reset_request_view(request):
    """Demande de réinitialisation de mot de passe"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        telephone = request.POST.get('telephone', '').strip()
        
        if not telephone:
            messages.error(request, "Veuillez saisir votre numéro de téléphone.")
            return render(request, 'authentication/password_reset_request.html')
        
        try:
            user = CustomUser.objects.get(telephone=telephone)
            
            # Générer un code de 6 chiffres
            import random
            code = str(random.randint(100000, 999999))
            
            # Supprimer les anciens tokens non utilisés
            from .models import PasswordResetToken
            PasswordResetToken.objects.filter(user=user, used=False).delete()
            
            # Créer un nouveau token
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=code
            )
            
            # Envoyer le code par SMS/WhatsApp
            try:
                from notifications_app.services import NotificationService
                message = f"TS Air Cargo: Votre code de réinitialisation est {code}. Ce code expire dans 24h."
                
                NotificationService.send_sms(
                    telephone=user.telephone,
                    message=message
                )
                
                messages.success(request, f"Un code de réinitialisation a été envoyé au {user.telephone}.")
                return redirect('authentication:password_reset_verify', user_id=user.id)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'envoi du SMS: {str(e)}")
                reset_token.delete()
                
        except CustomUser.DoesNotExist:
            # Pour des raisons de sécurité, ne pas révéler que l'utilisateur n'existe pas
            messages.info(request, "Si ce numéro existe dans notre système, un code de réinitialisation a été envoyé.")
            
    return render(request, 'authentication/password_reset_request.html')


def password_reset_verify_view(request, user_id):
    """Vérification du code de réinitialisation"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, "Lien invalide.")
        return redirect('authentication:password_reset_request')
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        if not code:
            messages.error(request, "Veuillez saisir le code reçu.")
            return render(request, 'authentication/password_reset_verify.html', {'user': user})
        
        try:
            from .models import PasswordResetToken
            reset_token = PasswordResetToken.objects.get(
                user=user,
                token=code,
                used=False
            )
            
            if reset_token.is_expired():
                messages.error(request, "Le code a expiré. Veuillez demander un nouveau code.")
                reset_token.delete()
                return redirect('authentication:password_reset_request')
            
            # Code valide, rediriger vers la page de nouveau mot de passe
            return redirect('authentication:password_reset_confirm', user_id=user.id, token=reset_token.token)
            
        except PasswordResetToken.DoesNotExist:
            messages.error(request, "Code invalide ou expiré.")
    
    return render(request, 'authentication/password_reset_verify.html', {'user': user})


def password_reset_confirm_view(request, user_id, token):
    """Définir un nouveau mot de passe"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    try:
        user = CustomUser.objects.get(id=user_id)
        from .models import PasswordResetToken
        reset_token = PasswordResetToken.objects.get(
            user=user,
            token=token,
            used=False
        )
        
        if reset_token.is_expired():
            messages.error(request, "Le lien a expiré. Veuillez recommencer le processus.")
            reset_token.delete()
            return redirect('authentication:password_reset_request')
            
    except (CustomUser.DoesNotExist, PasswordResetToken.DoesNotExist):
        messages.error(request, "Lien invalide ou expiré.")
        return redirect('authentication:password_reset_request')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            messages.error(request, "Veuillez remplir tous les champs.")
            return render(request, 'authentication/password_reset_confirm.html', {'user': user})
        
        if new_password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'authentication/password_reset_confirm.html', {'user': user})
        
        if len(new_password) < 6:
            messages.error(request, "Le mot de passe doit contenir au moins 6 caractères.")
            return render(request, 'authentication/password_reset_confirm.html', {'user': user})
        
        # Mettre à jour le mot de passe
        user.set_password(new_password)
        # Marquer que l'utilisateur a changé son mot de passe par défaut
        user.has_changed_default_password = True
        user.save()
        
        # Marquer le token comme utilisé
        reset_token.used = True
        reset_token.save()
        
        messages.success(request, "Votre mot de passe a été réinitialisé avec succès ! Vous pouvez maintenant vous connecter.")
        return redirect('authentication:login_client')
    
    return render(request, 'authentication/password_reset_confirm.html', {'user': user})
