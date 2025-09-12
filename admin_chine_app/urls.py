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
]
