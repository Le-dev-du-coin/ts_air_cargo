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
    # Vue supprimée: admin_chine_login_view n'est plus nécessaire
    
    # URL générique pour le login basé sur le rôle
    path('login/<str:role>/', views.role_based_login_view, name='role_based_login'),
    
    # Vérification OTP
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('otp-status/', views.otp_status_ajax, name='otp_status_ajax'),
    
    # Réinitialisation de mot de passe
    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password-reset/verify/', views.password_reset_verify_view, name='password_reset_verify'),
    path('password-reset/confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),
    
    # Déconnexion
    path('logout/', views.logout_view, name='logout'),
]
