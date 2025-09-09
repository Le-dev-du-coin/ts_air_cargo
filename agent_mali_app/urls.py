from django.urls import path
from . import views

app_name = 'agent_mali'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Gestion des lots
    path('lots-en-transit/', views.lots_en_transit_view, name='lots_en_transit'),
    path('recevoir-lot/<int:lot_id>/', views.recevoir_lot_view, name='recevoir_lot'),
    
    # Gestion des livraisons
    path('colis-a-livrer/', views.colis_a_livrer_view, name='colis_a_livrer'),
    path('marquer-livre/<int:colis_id>/', views.marquer_livre_view, name='marquer_livre'),
    path('marquer-perdu/<int:colis_id>/', views.marquer_perdu_view, name='marquer_perdu'),
    path('api/colis-details/<int:colis_id>/', views.colis_details_api, name='colis_details_api'),
    
    # Gestion des paiements
    path('colis-attente-paiement/', views.colis_attente_paiement_view, name='colis_attente_paiement'),
    path('marquer-paiement/<int:colis_id>/', views.marquer_paiement_view, name='marquer_paiement'),
    
    # Gestion des dépenses
    path('depenses/', views.depenses_view, name='depenses'),
    path('depenses/nouveau/', views.depense_create_view, name='depense_create'),
    path('nouvelle-depense/', views.nouvelle_depense_view, name='nouvelle_depense'),
    path('depenses/modifier/<int:depense_id>/', views.depense_edit_view, name='depense_edit'),
    path('depenses/supprimer/<int:depense_id>/', views.depense_delete_view, name='depense_delete'),
    path('depenses/detail/<int:depense_id>/', views.depense_detail_view, name='depense_detail'),
    
    # Rapports
    path('rapports/', views.rapports_view, name='rapports'),
    
    # API pour les rapports
    path('api/generate-daily-report/', views.generate_daily_report_api, name='generate_daily_report_api'),
    path('api/generate-monthly-report/', views.generate_monthly_report_api, name='generate_monthly_report_api'),
    path('api/generate-yearly-report/', views.generate_yearly_report_api, name='generate_yearly_report_api'),
    path('api/send-report-whatsapp/', views.send_report_whatsapp_api, name='send_report_whatsapp_api'),
    path('api/send-report-email/', views.send_report_email_api, name='send_report_email_api'),
    path('api/schedule-auto-report/', views.schedule_auto_report_api, name='schedule_auto_report_api'),
]
