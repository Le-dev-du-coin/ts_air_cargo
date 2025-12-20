from django.urls import path
from . import views
from . import whatsapp_views
from . import views_password_reset_sms
from . import views_send_sms

app_name = 'agent_chine'

urlpatterns = [
    # Tableau de bord Agent Chine
    path('', views.dashboard_view, name='dashboard'),
    
    # Gestion des clients
    path('clients/', views.client_list_view, name='client_list'),
    path('clients/create/', views.client_create_view, name='client_create'),
    path('clients/<int:client_id>/', views.client_detail_view, name='client_detail'),
    path('clients/<int:client_id>/edit/', views.client_edit_view, name='client_edit'),
    path('clients/export-csv/', views.export_clients_csv, name='export_clients_csv'),
    path('clients/<int:client_id>/reset-password/', views.client_reset_password_view, name='client_reset_password'),  # POST only
    path('clients/<int:client_id>/reset-password-sms/', views_password_reset_sms.client_reset_password_sms_view, name='client_reset_password_sms'),  # POST only - SMS uniquement
    path('clients/<int:client_id>/send-sms/', views_send_sms.send_custom_sms_view, name='send_custom_sms'),  # GET + POST - Envoyer SMS personnalisé
    path('clients/<int:client_id>/send-sms-ajax/', views_send_sms.send_sms_ajax, name='send_sms_ajax'),  # POST only - Version AJAX
    
    # Gestion des lots
    path('lots/', views.lot_list_view, name='lot_list'),
    path('lots/create/', views.lot_create_view, name='lot_create'),
    path('lots/<int:lot_id>/', views.lot_detail_view, name='lot_detail'),
    path('lots/<int:lot_id>/close/', views.lot_close_view, name='lot_close'),
    path('lots/<int:lot_id>/expedite/', views.lot_expedite_view, name='lot_expedite'),
    path('lots/<int:lot_id>/retry-notifications/', views.retry_lot_notifications, name='retry_lot_notifications'),
    path('api/lots/<int:lot_id>/notifications/count/', views.lot_notifications_count_api, name='lot_notifications_count'),
    
    # Gestion des colis
    path('colis/', views.colis_list_view, name='colis_list'),
    path('lots/<int:lot_id>/colis/create/', views.colis_create_view, name='colis_create'),
    path('colis/<int:colis_id>/', views.colis_detail_view, name='colis_detail'),
    path('colis/<int:colis_id>/edit/', views.colis_edit_view, name='colis_edit'),
    path('colis/<int:colis_id>/delete/', views.colis_delete_view, name='colis_delete'),
    path('colis/export-csv/', views.export_colis_csv, name='export_colis_csv'),
    
    # API pour calcul de prix automatique
    path('api/calculate-price/', views.calculate_price_api, name='calculate_price_api'),
    
    # Gestion des tâches asynchrones de colis
    path('tasks/', views.colis_task_list, name='colis_task_list'),
    path('tasks/<str:task_id>/', views.colis_task_status, name='colis_task_status'),
    path('tasks/<str:task_id>/retry/', views.colis_task_retry, name='colis_task_retry'),
    path('tasks/<str:task_id>/cancel/', views.colis_task_cancel, name='colis_task_cancel'),
    path('api/tasks/<str:task_id>/status/', views.colis_task_api_status, name='colis_task_api_status'),
    
    # Gestion des tâches de création client
    path('client-tasks/', views.client_creation_tasks_list, name='client_creation_tasks_list'),
    path('client-tasks/<str:task_id>/', views.client_creation_task_detail, name='client_creation_task_detail'),
    
    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),
    
    # Rapports
    path('reports/', views.reports_view, name='reports'),
    
    # Monitoring WaChap
    path('monitoring/wachap/', views.wachap_monitoring_view, name='wachap_monitoring'),
    
    # === Gestion automatique des comptes clients ===
    # API pour créer automatiquement un compte client
    path('api/create-client-account/', views.create_client_account_api, name='create_client_account_api'),
    
    # API pour renvoyer les identifiants
    path('api/clients/<int:client_id>/resend-credentials/', views.resend_client_credentials_api, name='resend_client_credentials_api'),
    
    # API pour vérifier si un client existe
    path('api/check-client-exists/', views.check_client_exists_api, name='check_client_exists_api'),
    
    # API pour récupérer les informations d'un client
    path('api/clients/<int:client_id>/info/', views.client_info_api, name='client_info_api'),
    
    # API de recherche clients pour Select2
    path('api/clients/search/', views.clients_search_api, name='clients_search_api'),
    
    # Liste des comptes utilisateurs clients
    path('user-clients/', views.user_clients_list, name='user_clients_list'),
    
    # === Monitoring WhatsApp pour Agent Chine ===
    path('whatsapp/monitoring/', whatsapp_views.whatsapp_monitoring_dashboard, name='whatsapp_monitoring'),
    path('whatsapp/monitoring/list/', whatsapp_views.whatsapp_monitoring_list, name='whatsapp_monitoring_list'),
    path('whatsapp/monitoring/retry/', whatsapp_views.retry_failed_notifications, name='whatsapp_retry_failed'),
    path('whatsapp/monitoring/<int:attempt_id>/', whatsapp_views.whatsapp_attempt_details, name='whatsapp_attempt_details'),
    path('api/whatsapp/monitoring/stats/', whatsapp_views.monitoring_stats_api, name='whatsapp_monitoring_stats_api'),
]
