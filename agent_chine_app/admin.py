from django.contrib import admin
from .models import Client, Lot, Colis

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['user', 'pays', 'date_creation']
    list_filter = ['pays', 'date_creation']
    search_fields = ['user__first_name', 'user__last_name', 'user__telephone', 'adresse']
    raw_id_fields = ['user']

@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ['numero_lot', 'statut', 'prix_transport', 'agent_createur', 'date_creation']
    list_filter = ['statut', 'date_creation', 'agent_createur']
    search_fields = ['numero_lot']
    readonly_fields = ['numero_lot', 'date_creation']
    raw_id_fields = ['agent_createur']

@admin.register(Colis)
class ColisAdmin(admin.ModelAdmin):
    list_display = ['numero_suivi', 'client', 'lot', 'statut', 'poids', 'prix_calcule', 'date_creation']
    list_filter = ['statut', 'mode_paiement', 'date_creation']
    search_fields = ['numero_suivi', 'client__user__first_name', 'client__user__last_name', 'client__user__telephone']
    readonly_fields = ['numero_suivi', 'prix_calcule', 'date_creation']
    raw_id_fields = ['client', 'lot']
