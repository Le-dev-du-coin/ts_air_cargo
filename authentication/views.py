from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from .models import CustomUser
from .forms import LoginForm, RegistrationForm


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

def register_view(request):
    """Vue d'inscription pour les nouveaux clients"""
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Créer le nouvel utilisateur
            user = form.save()
            messages.success(request, f"Compte créé avec succès ! Bienvenue {user.get_full_name()}!")
            
            # Connecter automatiquement l'utilisateur après inscription
            login(request, user)
            return redirect(get_dashboard_url_by_role(user))
    else:
        form = RegistrationForm()
    
    return render(request, 'authentication/register.html', {'form': form})


def home_view(request):
    """Page d'accueil avec liens de connexion par rôle"""
    # Si l'utilisateur est déjà connecté, le rediriger vers son dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_by_role(request.user))
    return render(request, 'authentication/home.html')
