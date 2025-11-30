from django.urls import path
from . import views

app_name = 'admin_chine_app'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    path('dashboard-admin/', views.dashboard_admin_view, name='dashboard_admin'),
    
    # Gestion des transferts d'argent
    path('transferts/', views.transferts_list, name='transferts'),
    path('transferts/<int:transfert_id>/', views.transfert_detail, name='transfert_detail'),
    # path('transferts/<int:transfert_id>/modifier/', views.transfert_edit, name='transfert_edit'),
    
    # Gestion des transferts - routes supplémentaires
    # path('transferts/<int:transfert_id>/supprimer/', views.transfert_delete, name='transfert_delete'),
    
    # Gestion des agents
    path('agents/', views.agents_list, name='agents'),
    path('agents/nouveau/', views.agent_create, name='agent_create'),
    path('agents/<int:agent_id>/modifier/', views.agent_edit, name='agent_edit'),
    path('agents/<int:agent_id>/supprimer/', views.agent_delete, name='agent_delete'),
    
    
    # Gestion des tarifs
    path('tarifs/', views.tarifs_list, name='tarifs'),
    path('tarifs/nouveau/', views.tarif_create, name='tarif_create'),
    path('tarifs/<int:tarif_id>/', views.tarif_detail, name='tarif_detail'),
    path('tarifs/<int:tarif_id>/modifier/', views.tarif_edit, name='tarif_edit'),
    path('tarifs/<int:tarif_id>/supprimer/', views.tarif_delete, name='tarif_delete'),
    
    # Rapports financiers
    path('rapports/', views.rapports, name='rapports'),
    
    # Paramètres système
    path('parametres/', views.parametres, name='parametres'),
    
    # Export Excel
    path('export-rapport-excel/', views.export_rapport_excel, name='export_rapport_excel'),
    
    # Exports spécialisés
    path('export-depenses-excel/', views.export_depenses_excel, name='export_depenses_excel'),
    path('export-rapport-cargo-excel/', views.export_rapport_cargo_excel, name='export_rapport_cargo_excel'),
    path('export-rapport-express-excel/', views.export_rapport_express_excel, name='export_rapport_express_excel'),
    
    # === Monitoring WhatsApp Complet (Admin) ===
    # Import des vues depuis whatsapp_monitoring_app pour monitoring global
    path('whatsapp/monitoring/', views.whatsapp_admin_monitoring, name='whatsapp_monitoring'),
    
    # === Gestion CRUD des Lots (Admin Chine) ===
    path('lots/', views.lots_list, name='lots_list'),
    path('lots/create/', views.lot_create, name='lot_create'),
    path('lots/<int:lot_id>/', views.lot_detail, name='lot_detail'),
    path('lots/<int:lot_id>/edit/', views.lot_edit, name='lot_edit'),
    path('lots/<int:lot_id>/delete/', views.lot_delete, name='lot_delete'),
    path('lots/<int:lot_id>/change-status/', views.lot_change_status, name='lot_change_status'),
    
    # === Gestion CRUD des Colis (Admin Chine) - DÉSACTIVÉ ===
    # Gestion des colis se fait maintenant dans lot_detail
    # path('colis/', views.colis_list, name='colis_list'),
    # path('colis/create/', views.colis_create, name='colis_create'),
    # path('colis/<int:colis_id>/', views.colis_detail, name='colis_detail'),
    # path('colis/<int:colis_id>/edit/', views.colis_edit, name='colis_edit'),
    # path('colis/<int:colis_id>/delete/', views.colis_delete, name='colis_delete'),
    
    # === Gestion des Clients (Admin Chine) - DÉSACTIVÉ ===
    # path('clients/', views.clients_list, name='clients_list'),
    # path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
]
