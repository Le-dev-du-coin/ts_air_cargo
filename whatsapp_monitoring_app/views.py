from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from .models import WhatsAppMessageAttempt, WhatsAppWebhookLog
from .services import WhatsAppMonitoringService
import logging

logger = logging.getLogger(__name__)


@login_required
def whatsapp_monitoring_dashboard_admin(request):
    """
    Dashboard de monitoring WhatsApp complet pour admin
    Affiche toutes les notifications de toutes les apps
    """
    try:
        # Toutes les tentatives (pas de filtre par source_app)
        all_attempts = WhatsAppMessageAttempt.objects.all()
        
        # Statistiques générales globales
        stats = {
            'total_attempts': all_attempts.count(),
            'successful': all_attempts.filter(status='sent').count(),
            'failed': all_attempts.filter(status='failed').count(),
            'pending': all_attempts.filter(status='pending').count(),
            'in_retry': all_attempts.filter(status='retry').count(),
        }
        
        # Calcul du taux de succès
        if stats['total_attempts'] > 0:
            stats['success_rate'] = round((stats['successful'] / stats['total_attempts']) * 100, 1)
        else:
            stats['success_rate'] = 0
        
        # Statistiques par app source
        stats_by_app = all_attempts.values('source_app').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent')),
            failed_count=Count('id', filter=Q(status='failed')),
            pending_count=Count('id', filter=Q(status='pending'))
        ).order_by('-count')
        
        # Statistiques par type de message
        message_types = all_attempts.values('message_type').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Statistiques par catégorie
        categories = all_attempts.values('category').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Dernières tentatives (limit 15 pour admin)
        recent_attempts = all_attempts.select_related(
            'user'
        ).order_by('-created_at')[:15]
        
        # Notifications en échec qui nécessitent une attention
        failed_attempts = all_attempts.filter(
            status='failed',
            retry_count__gte=3
        ).select_related('user').order_by('-updated_at')[:10]
        
        # Statistiques par période
        from datetime import timedelta
        now = timezone.now()
        stats_by_period = {
            'last_24h': all_attempts.filter(
                created_at__gte=now - timedelta(hours=24)
            ).count(),
            'last_7days': all_attempts.filter(
                created_at__gte=now - timedelta(days=7)
            ).count(),
            'last_30days': all_attempts.filter(
                created_at__gte=now - timedelta(days=30)
            ).count(),
        }
        
        context = {
            'app_name': 'Administration',
            'source_app': 'admin',
            'is_admin_view': True,
            'stats': stats,
            'stats_by_app': stats_by_app,
            'stats_by_period': stats_by_period,
            'message_types': message_types,
            'categories': categories,
            'recent_attempts': recent_attempts,
            'failed_attempts': failed_attempts,
        }
        
        return render(request, 'whatsapp_monitoring_app/admin_monitoring.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dashboard monitoring admin: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement du monitoring: {str(e)}")
        return render(request, 'whatsapp_monitoring_app/admin_monitoring.html', {
            'app_name': 'Administration',
            'source_app': 'admin',
            'is_admin_view': True,
            'stats': {},
            'error': str(e)
        })


@login_required
def retry_all_failed_notifications(request):
    """
    Relance toutes les notifications WhatsApp en échec (admin seulement)
    """
    if request.method == 'POST':
        try:
            # Traiter les retries pour toutes les apps
            stats = WhatsAppMonitoringService.process_pending_retries(
                source_app=None,  # Toutes les apps
                max_retries_per_run=100  # Plus pour admin
            )
            
            messages.success(
                request, 
                f"Relance globale terminée: {stats['processed']} tentatives traitées, "
                f"{stats['success']} succès, {stats['failed']} échecs"
            )
            
            return JsonResponse({
                'success': True,
                'message': f"{stats['success']} notifications relancées avec succès (global)",
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Erreur relance notifications globale: {e}", exc_info=True)
            messages.error(request, f"Erreur lors de la relance globale: {str(e)}")
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
