from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Page d'accueil avec sélection de rôle
    path('', views.home_view, name='home'),
    
    # Connexion générale
    path('login/', views.login_view, name='login'),
    
    # Connexions par rôle spécifique
    path('login/client/', views.role_based_login_view, {'role': 'client'}, name='login_client'),
    path('login/agent-chine/', views.role_based_login_view, {'role': 'agent_chine'}, name='login_agent_chine'),
    path('login/agent-mali/', views.role_based_login_view, {'role': 'agent_mali'}, name='login_agent_mali'),
    path('login/admin/', views.role_based_login_view, {'role': 'admin'}, name='login_admin'),
    path('login/admin-mali/', views.role_based_login_view, {'role': 'admin_mali'}, name='login_admin_mali'),
    
    # URL générique pour le login basé sur le rôle
    path('login/<str:role>/', views.role_based_login_view, name='role_based_login'),
    
    # Inscription pour les clients
    path('register/', views.register_view, name='register'),
    
    # Déconnexion
    path('logout/', views.logout_view, name='logout'),
]
