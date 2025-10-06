from django.urls import path
from . import views
from . import whatsapp_integration

app_name = 'agent_mali'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Gestion des lots
    path('lots-en-transit/', views.lots_en_transit_view, name='lots_en_transit'),
    path('lots-livres/', views.lots_livres_view, name='lots_livres'),
    path('recevoir-lot/<int:lot_id>/', views.recevoir_lot_view, name='recevoir_lot'),
    
    # Gestion des livraisons
    path('colis-a-livrer/', views.colis_a_livrer_view, name='colis_a_livrer'),
    path('marquer-livre/<int:colis_id>/', views.marquer_livre_view, name='marquer_livre'),
    path('marquer-perdu/<int:colis_id>/', views.marquer_perdu_view, name='marquer_perdu'),
    path('api/colis-details/<int:colis_id>/', views.colis_details_api, name='colis_details_api'),
    
    # Gestion des paiements
    path('colis-attente-paiement/', views.colis_attente_paiement_view, name='colis_attente_paiement'),
    path('marquer-paiement/<int:colis_id>/', views.marquer_paiement_view, name='marquer_paiement'),
    
    # Ajustements de prix (JC et Remises)
    path('colis/<int:colis_id>/detail/', views.colis_detail_view, name='colis_detail'),
    path('colis/<int:colis_id>/ajuster-prix/', views.appliquer_ajustement_view, name='appliquer_ajustement'),
    path('ajustement/<int:adjustment_id>/annuler/', views.annuler_ajustement_view, name='annuler_ajustement'),
    path('ajustements-rapport/', views.ajustements_rapport_view, name='ajustements_rapport'),
    
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
    
    # Exports Excel
    path('export-depenses-excel/', views.export_depenses_excel, name='export_depenses_excel'),
    path('export-rapport-cargo-excel/', views.export_rapport_cargo_excel, name='export_rapport_cargo_excel'),
    path('export-rapport-express-excel/', views.export_rapport_express_excel, name='export_rapport_express_excel'),
    path('export-rapport-bateau-excel/', views.export_rapport_bateau_excel, name='export_rapport_bateau_excel'),
    
    # === Monitoring WhatsApp pour Agent Mali ===
    path('whatsapp/monitoring/', whatsapp_integration.whatsapp_monitoring_dashboard, name='whatsapp_monitoring'),
    path('whatsapp/monitoring/list/', whatsapp_integration.whatsapp_monitoring_list, name='whatsapp_monitoring_list'),
    path('whatsapp/monitoring/retry/', whatsapp_integration.retry_failed_notifications, name='whatsapp_retry_failed'),
]
