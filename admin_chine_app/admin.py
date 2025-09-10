from django.contrib import admin
from .models import InventoryChina, OperationChina

@admin.register(InventoryChina)
class InventoryChinaAdmin(admin.ModelAdmin):
    list_display = ['nom_produit', 'code_produit', 'categorie', 'fournisseur_nom', 'quantite_stock', 'prix_unitaire_yuan', 'statut', 'date_creation']
    list_filter = ['categorie', 'statut', 'date_creation']
    search_fields = ['nom_produit', 'code_produit', 'fournisseur_nom']
    readonly_fields = ['prix_unitaire_fcfa', 'date_creation', 'date_modification']
    
    fieldsets = (
        ('Informations Produit', {
            'fields': ('nom_produit', 'code_produit', 'categorie', 'description', 'image_produit')
        }),
        ('Fournisseur', {
            'fields': ('fournisseur_nom', 'fournisseur_contact')
        }),
        ('Prix et Change', {
            'fields': ('prix_unitaire_yuan', 'taux_change_utilise', 'prix_unitaire_fcfa')
        }),
        ('Stock', {
            'fields': ('quantite_stock', 'quantite_minimale', 'poids_unitaire', 'statut')
        }),
        ('Suivi', {
            'fields': ('admin_createur', 'date_creation', 'date_modification')
        }),
    )

@admin.register(OperationChina)
class OperationChinaAdmin(admin.ModelAdmin):
    list_display = ['numero_operation', 'type_operation', 'produit', 'quantite', 'montant_total', 'monnaie', 'statut', 'date_operation']
    list_filter = ['type_operation', 'statut', 'monnaie', 'date_operation']
    search_fields = ['numero_operation', 'description', 'reference_externe']
    readonly_fields = ['numero_operation', 'montant_total', 'date_creation', 'date_modification']
    
    fieldsets = (
        ('Opération', {
            'fields': ('numero_operation', 'type_operation', 'produit', 'quantite')
        }),
        ('Financier', {
            'fields': ('prix_unitaire', 'montant_total', 'monnaie')
        }),
        ('Détails', {
            'fields': ('description', 'fournisseur_contact', 'reference_externe')
        }),
        ('Suivi', {
            'fields': ('admin_responsable', 'statut', 'date_operation', 'date_creation', 'date_modification')
        }),
    )
