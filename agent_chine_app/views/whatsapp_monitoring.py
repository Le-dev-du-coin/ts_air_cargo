"""
Vues pour le monitoring des notifications WhatsApp
dans l'application agent_chine
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
import json
import logging

from ..models.whatsapp_monitoring import WhatsAppMessageAttempt, WhatsAppWebhookLog
from ..services.whatsapp_monitoring import WhatsAppMonitoringService, WhatsAppRetryTask
from ..utils import agent_chine_required

logger = logging.getLogger(__name__)


@agent_chine_required
def whatsapp_monitoring_dashboard(request):
    """
    Dashboard principal pour le monitoring WhatsApp
    """
    # Statistiques générales
    stats = WhatsAppMonitoringService.get_monitoring_stats(days_back=7)
    
    # Messages récents
    recent_attempts = WhatsAppMessageAttempt.objects.select_related('user').order_by('-created_at')[:20]
    
    # Messages en attente de retry
    pending_retries = WhatsAppMessageAttempt.objects.filter(
        status='failed_retry',
        next_retry_at__lte=timezone.now()
    ).count()
    
    # Messages qui échouent fréquemment (plus de 2 tentatives)
    frequent_failures = WhatsAppMessageAttempt.objects.filter(
        attempt_count__gte=2,
        status__in=['failed_retry', 'failed_final']
    ).select_related('user').order_by('-last_attempt_at')[:10]
    
    context = {
        'stats': stats,
        'recent_attempts': recent_attempts,
        'pending_retries': pending_retries,
        'frequent_failures': frequent_failures,
        'page_title': 'Monitoring WhatsApp',
    }
    
    return render(request, 'agent_chine_app/monitoring/dashboard.html', context)


@agent_chine_required
def whatsapp_attempts_list(request):
    """
    Liste paginée des tentatives WhatsApp avec filtres
    """
    attempts = WhatsAppMessageAttempt.objects.select_related('user').order_by('-created_at')
    
    # Filtres
    status_filter = request.GET.get('status')
    message_type_filter = request.GET.get('message_type')
    phone_filter = request.GET.get('phone')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status_filter:
        attempts = attempts.filter(status=status_filter)
    
    if message_type_filter:
        attempts = attempts.filter(message_type=message_type_filter)
        
    if phone_filter:
        attempts = attempts.filter(phone_number__icontains=phone_filter)
    
    if date_from:
        try:
            date_from_parsed = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            attempts = attempts.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            messages.warning(request, "Format de date invalide pour 'Date de'")
    
    if date_to:
        try:
            date_to_parsed = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            attempts = attempts.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            messages.warning(request, "Format de date invalide pour 'Date à'")
    
    # Pagination
    paginator = Paginator(attempts, 25)
    page_number = request.GET.get('page')
    attempts_page = paginator.get_page(page_number)
    
    # Choix pour les filtres
    status_choices = WhatsAppMessageAttempt.STATUS_CHOICES
    message_type_choices = WhatsAppMessageAttempt.MESSAGE_TYPE_CHOICES
    
    context = {
        'attempts': attempts_page,
        'status_choices': status_choices,
        'message_type_choices': message_type_choices,
        'current_filters': {
            'status': status_filter,
            'message_type': message_type_filter,
            'phone': phone_filter,
            'date_from': date_from,
            'date_to': date_to,
        },
        'page_title': 'Tentatives WhatsApp',
    }
    
    return render(request, 'agent_chine_app/monitoring/attempts_list.html', context)


@agent_chine_required
def whatsapp_attempt_detail(request, attempt_id):
    """
    Détail d'une tentative WhatsApp avec historique
    """
    attempt = get_object_or_404(WhatsAppMessageAttempt, id=attempt_id)
    
    # Webhooks associés
    webhooks = attempt.webhooks.order_by('-received_at')
    
    # Actions possibles
    can_retry = attempt.can_retry()
    can_cancel = attempt.status in ['pending', 'failed_retry']
    
    context = {
        'attempt': attempt,
        'webhooks': webhooks,
        'can_retry': can_retry,
        'can_cancel': can_cancel,
        'page_title': f'Tentative {attempt.id}',
    }
    
    return render(request, 'agent_chine_app/monitoring/attempt_detail.html', context)


@agent_chine_required
@require_http_methods(["POST"])
def whatsapp_retry_attempt(request, attempt_id):
    """
    Force le retry d'une tentative spécifique
    """
    attempt = get_object_or_404(WhatsAppMessageAttempt, id=attempt_id)
    
    if not attempt.can_retry():
        messages.error(request, "Cette tentative ne peut pas être relancée.")
        return redirect('agent_chine:whatsapp_attempt_detail', attempt_id=attempt_id)
    
    try:
        # Forcer le retry immédiatement
        success, message_id, error_message = WhatsAppMonitoringService.send_message_attempt(attempt)
        
        if success:
            messages.success(request, f"Message envoyé avec succès ! ID: {message_id}")
        else:
            messages.error(request, f"Échec du retry: {error_message}")
            
    except Exception as e:
        logger.error(f"Erreur lors du retry manuel de {attempt_id}: {str(e)}")
        messages.error(request, f"Erreur technique: {str(e)}")
    
    return redirect('agent_chine:whatsapp_attempt_detail', attempt_id=attempt_id)


@agent_chine_required
@require_http_methods(["POST"])
def whatsapp_cancel_attempt(request, attempt_id):
    """
    Annule une tentative en attente
    """
    attempt = get_object_or_404(WhatsAppMessageAttempt, id=attempt_id)
    
    if attempt.status not in ['pending', 'failed_retry']:
        messages.error(request, "Cette tentative ne peut pas être annulée.")
        return redirect('agent_chine:whatsapp_attempt_detail', attempt_id=attempt_id)
    
    try:
        attempt.cancel()
        messages.success(request, "Tentative annulée avec succès.")
        logger.info(f"Tentative {attempt_id} annulée manuellement par {request.user.username}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'annulation de {attempt_id}: {str(e)}")
        messages.error(request, f"Erreur lors de l'annulation: {str(e)}")
    
    return redirect('agent_chine:whatsapp_attempt_detail', attempt_id=attempt_id)


@agent_chine_required
@require_http_methods(["POST"])
def whatsapp_bulk_retry(request):
    """
    Lance le traitement en lot des retries
    """
    try:
        # Lancer le traitement des retries
        stats = WhatsAppMonitoringService.process_pending_retries()
        
        messages.success(
            request, 
            f"Traitement terminé: {stats['processed']} messages traités, "
            f"{stats['success']} succès, {stats['failed']} échecs"
        )
        
        if stats['errors']:
            for error in stats['errors'][:5]:  # Afficher seulement les 5 premières erreurs
                messages.warning(request, error)
        
        logger.info(f"Retry en lot lancé par {request.user.username}: {stats}")
        
    except Exception as e:
        logger.error(f"Erreur lors du retry en lot: {str(e)}")
        messages.error(request, f"Erreur lors du traitement: {str(e)}")
    
    return redirect('agent_chine:whatsapp_monitoring_dashboard')


@agent_chine_required
def whatsapp_stats_api(request):
    """
    API pour récupérer les statistiques en temps réel (pour AJAX)
    """
    days_back = int(request.GET.get('days', 7))
    
    try:
        stats = WhatsAppMonitoringService.get_monitoring_stats(days_back=days_back)
        
        # Messages en attente de retry
        pending_retries = WhatsAppMessageAttempt.objects.filter(
            status='failed_retry',
            next_retry_at__lte=timezone.now()
        ).count()
        
        stats['pending_retries'] = pending_retries
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Erreur API stats WhatsApp: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_webhook_receiver(request):
    """
    Endpoint pour recevoir les webhooks des providers WhatsApp
    Public endpoint (pas de login requis)
    """
    try:
        # Parser le payload JSON
        payload = json.loads(request.body.decode('utf-8'))
        
        # Extraire les informations du webhook
        provider_message_id = payload.get('message_id') or payload.get('id')
        webhook_type = payload.get('type', 'unknown')
        status = payload.get('status', 'unknown')
        
        if not provider_message_id:
            logger.warning(f"Webhook reçu sans message_id: {payload}")
            return JsonResponse({'success': False, 'error': 'message_id manquant'})
        
        # Traiter le webhook
        success = WhatsAppMonitoringService.process_webhook(
            provider_message_id=provider_message_id,
            webhook_type=webhook_type,
            status=status,
            raw_payload=payload
        )
        
        if success:
            logger.info(f"Webhook traité avec succès: {webhook_type} pour {provider_message_id}")
            return JsonResponse({'success': True})
        else:
            logger.error(f"Échec traitement webhook: {webhook_type} pour {provider_message_id}")
            return JsonResponse({'success': False, 'error': 'Échec traitement'})
            
    except json.JSONDecodeError:
        logger.error("Webhook reçu avec JSON invalide")
        return JsonResponse({'success': False, 'error': 'JSON invalide'})
        
    except Exception as e:
        logger.error(f"Erreur webhook WhatsApp: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
def whatsapp_admin_cleanup(request):
    """
    Interface d'administration pour nettoyer les anciennes tentatives
    Accessible seulement aux staff members
    """
    if request.method == 'POST':
        days_old = int(request.POST.get('days_old', 30))
        
        try:
            deleted_count = WhatsAppRetryTask.cleanup_old_attempts(days_old=days_old)
            
            messages.success(
                request,
                f"Nettoyage terminé: {deleted_count} tentatives anciennes supprimées "
                f"(plus de {days_old} jours)"
            )
            
            logger.info(f"Nettoyage WhatsApp par {request.user.username}: {deleted_count} supprimées")
            
        except Exception as e:
            logger.error(f"Erreur nettoyage WhatsApp: {str(e)}")
            messages.error(request, f"Erreur lors du nettoyage: {str(e)}")
    
    # Statistiques pour l'interface
    total_attempts = WhatsAppMessageAttempt.objects.count()
    old_attempts_30 = WhatsAppMessageAttempt.objects.filter(
        created_at__lt=timezone.now() - timezone.timedelta(days=30),
        status__in=['sent', 'delivered', 'failed_final', 'cancelled']
    ).count()
    
    context = {
        'total_attempts': total_attempts,
        'old_attempts_30': old_attempts_30,
        'page_title': 'Administration WhatsApp',
    }
    
    return render(request, 'agent_chine_app/monitoring/admin_cleanup.html', context)
