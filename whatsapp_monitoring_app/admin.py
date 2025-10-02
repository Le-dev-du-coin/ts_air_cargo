"""
Interface d'administration pour le monitoring WhatsApp
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import WhatsAppMessageAttempt, WhatsAppWebhookLog
from .services import WhatsAppMonitoringService


@admin.register(WhatsAppMessageAttempt)
class WhatsAppMessageAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'phone_number', 'user_display', 'source_app', 'message_type', 
        'status_display', 'priority', 'attempt_count', 'created_at', 'actions'
    ]
    list_filter = [
        'status', 'source_app', 'message_type', 'priority', 
        'created_at', 'attempt_count'
    ]
    search_fields = ['phone_number', 'user__first_name', 'user__last_name', 'title', 'category']
    readonly_fields = [
        'created_at', 'first_attempt_at', 'last_attempt_at', 'sent_at', 
        'delivered_at', 'provider_message_id', 'provider_response'
    ]
    fieldsets = [
        ('Informations générales', {
            'fields': (
                'user', 'phone_number', 'source_app', 'message_type', 
                'category', 'priority', 'title'
            )
        }),
        ('Contenu', {
            'fields': ('message_content',)
        }),
        ('Statut et tentatives', {
            'fields': (
                'status', 'attempt_count', 'max_attempts', 
                'retry_delay_seconds', 'exponential_backoff'
            )
        }),
        ('Dates importantes', {
            'fields': (
                'created_at', 'first_attempt_at', 'last_attempt_at', 
                'next_retry_at', 'sent_at', 'delivered_at'
            )
        }),
        ('Réponse provider', {
            'fields': ('provider_message_id', 'provider_response')
        }),
        ('Erreurs', {
            'fields': ('error_message', 'error_code')
        }),
        ('Métadonnées', {
            'fields': ('sender_role', 'region_override', 'context_data')
        }),
    ]
    
    def user_display(self, obj):
        if obj.user:
            return f"{obj.user.get_full_name()} ({obj.user.username})"
        return "Aucun utilisateur"
    user_display.short_description = "Utilisateur"
    
    def status_display(self, obj):
        status_colors = {
            'pending': '#ffc107',  # Jaune
            'sending': '#17a2b8',  # Bleu
            'sent': '#28a745',     # Vert
            'delivered': '#20c997', # Vert teal
            'failed': '#dc3545',   # Rouge
            'failed_retry': '#fd7e14', # Orange
            'failed_final': '#6f42c1', # Violet
            'cancelled': '#6c757d',    # Gris
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Statut"
    
    def actions(self, obj):
        actions = []
        if obj.can_retry():
            retry_url = reverse('admin:whatsapp_monitoring_app_whatsappmessageattempt_change', args=[obj.pk])
            actions.append(f'<a href="{retry_url}" style="color: #17a2b8;">🔄 Retry</a>')
        
        if obj.status in ['pending', 'failed_retry']:
            actions.append('<span style="color: #dc3545;">❌ Annuler</span>')
        
        return format_html(' | '.join(actions))
    actions.short_description = "Actions"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(WhatsAppWebhookLog)
class WhatsAppWebhookLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'provider_message_id', 'webhook_type', 'status', 
        'processed', 'received_at', 'message_attempt_link'
    ]
    list_filter = ['webhook_type', 'status', 'processed', 'received_at']
    search_fields = ['provider_message_id', 'webhook_type', 'status']
    readonly_fields = ['received_at', 'processed_at']
    
    fieldsets = [
        ('Informations webhook', {
            'fields': ('provider_message_id', 'webhook_type', 'status')
        }),
        ('Traitement', {
            'fields': ('processed', 'processing_error', 'received_at', 'processed_at')
        }),
        ('Données brutes', {
            'fields': ('raw_payload',),
            'classes': ('collapse',)
        }),
        ('Tentative associée', {
            'fields': ('message_attempt',)
        })
    ]
    
    def message_attempt_link(self, obj):
        if obj.message_attempt:
            url = reverse('admin:whatsapp_monitoring_app_whatsappmessageattempt_change', 
                         args=[obj.message_attempt.pk])
            return format_html(
                '<a href="{}">{}</a>', 
                url, f"Tentative #{obj.message_attempt.id}"
            )
        return "Aucune tentative"
    message_attempt_link.short_description = "Tentative associée"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('message_attempt')


# Actions personnalisées pour l'admin
def retry_selected_attempts(modeladmin, request, queryset):
    """Action pour retry les tentatives sélectionnées"""
    retried_count = 0
    for attempt in queryset.filter(status__in=['failed', 'failed_retry']):
        if attempt.can_retry():
            try:
                WhatsAppMonitoringService.send_message_attempt(attempt)
                retried_count += 1
            except Exception as e:
                pass  # Ignorer les erreurs individuelles
    
    if retried_count > 0:
        modeladmin.message_user(
            request, 
            f"{retried_count} tentative(s) relancée(s) avec succès."
        )
    else:
        modeladmin.message_user(
            request, 
            "Aucune tentative n'a pu être relancée.",
            level='warning'
        )

retry_selected_attempts.short_description = "🔄 Relancer les tentatives sélectionnées"


def cancel_selected_attempts(modeladmin, request, queryset):
    """Action pour annuler les tentatives sélectionnées"""
    cancelled_count = 0
    for attempt in queryset.filter(status__in=['pending', 'failed_retry']):
        attempt.cancel()
        cancelled_count += 1
    
    if cancelled_count > 0:
        modeladmin.message_user(
            request, 
            f"{cancelled_count} tentative(s) annulée(s)."
        )
    else:
        modeladmin.message_user(
            request, 
            "Aucune tentative n'a été annulée.",
            level='warning'
        )

cancel_selected_attempts.short_description = "❌ Annuler les tentatives sélectionnées"


# Ajouter les actions à l'admin
WhatsAppMessageAttemptAdmin.actions = [retry_selected_attempts, cancel_selected_attempts]
