from django.urls import path
from . import views

app_name = 'client_app'

urlpatterns = [
    
    # Dashboard principal
    path('', views.dashboard_view, name='dashboard'),
    
    # Gestion des colis
    path('mes-colis/', views.mes_colis_view, name='mes_colis'),
    path('colis/<int:colis_id>/', views.colis_detail_view, name='colis_detail'),
    path('colis/<int:colis_id>/image/', views.colis_image_view, name='colis_image'),
    
    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    
    # Suivi de colis
    path('suivi/', views.suivi_colis_view, name='suivi_colis'),
    path('suivi/<str:numero_suivi>/', views.suivi_detail_view, name='suivi_detail'),
    
    # Paramètres et sécurité
    path('change-password/', views.change_password_view, name='change_password'),
    path('settings/', views.settings_view, name='settings'),
]
