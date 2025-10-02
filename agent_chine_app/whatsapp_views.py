"""
Vues pour le monitoring WhatsApp dans agent_chine_app
Affiche uniquement les notifications de l'app agent_chine
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from whatsapp_monitoring_app.models import WhatsAppMessageAttempt, WhatsAppWebhookLog
from whatsapp_monitoring_app.services import WhatsAppMonitoringService
import logging

logger = logging.getLogger(__name__)


@login_required
def whatsapp_monitoring_dashboard(request):
    """
    Dashboard de monitoring WhatsApp spécifique à agent_chine_app
    """
    try:
        # Filtrer uniquement les notifications de agent_chine
        agent_chine_attempts = WhatsAppMessageAttempt.objects.filter(source_app='agent_chine')
        
        # Statistiques générales pour agent_chine
        stats = {
            'total_attempts': agent_chine_attempts.count(),
            'successful': agent_chine_attempts.filter(status='sent').count(),
            'failed': agent_chine_attempts.filter(status='failed').count(),
            'pending': agent_chine_attempts.filter(status='pending').count(),
            'in_retry': agent_chine_attempts.filter(status='retry').count(),
        }
        
        # Calcul du taux de succès
        if stats['total_attempts'] > 0:
            stats['success_rate'] = round((stats['successful'] / stats['total_attempts']) * 100, 1)
        else:
            stats['success_rate'] = 0
        
        # Statistiques par type de message
        message_types = agent_chine_attempts.values('message_type').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Statistiques par catégorie
        categories = agent_chine_attempts.values('category').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Dernières tentatives (limit 10)
        recent_attempts = agent_chine_attempts.select_related(
            'user'
        ).order_by('-created_at')[:10]
        
        # Notifications en échec qui nécessitent une attention
        failed_attempts = agent_chine_attempts.filter(
            status='failed',
            retry_count__gte=3
        ).select_related('user').order_by('-updated_at')[:5]
        
        context = {
            'app_name': 'Agent Chine',
            'source_app': 'agent_chine',
            'stats': stats,
            'message_types': message_types,
            'categories': categories,
            'recent_attempts': recent_attempts,
            'failed_attempts': failed_attempts,
        }
        
        return render(request, 'agent_chine_app/whatsapp_monitoring.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dashboard monitoring agent_chine: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement du monitoring: {str(e)}")
        return render(request, 'agent_chine_app/whatsapp_monitoring.html', {
            'app_name': 'Agent Chine',
            'source_app': 'agent_chine',
            'stats': {},
            'error': str(e)
        })


@login_required  
def whatsapp_monitoring_list(request):
    """
    Liste paginée des tentatives WhatsApp pour agent_chine_app
    """
    try:
        # Filtres
        status_filter = request.GET.get('status', '')
        message_type_filter = request.GET.get('message_type', '')
        category_filter = request.GET.get('category', '')
        search = request.GET.get('search', '')
        
        # Query de base pour agent_chine seulement
        attempts = WhatsAppMessageAttempt.objects.filter(
            source_app='agent_chine'
        ).select_related('user')
        
        # Appliquer les filtres
        if status_filter:
            attempts = attempts.filter(status=status_filter)
        
        if message_type_filter:
            attempts = attempts.filter(message_type=message_type_filter)
            
        if category_filter:
            attempts = attempts.filter(category=category_filter)
            
        if search:
            attempts = attempts.filter(
                Q(user__telephone__icontains=search) |
                Q(user__nom__icontains=search) |
                Q(user__prenom__icontains=search) |
                Q(title__icontains=search) |
                Q(error_message__icontains=search)
            )
        
        # Ordonner par date décroissante
        attempts = attempts.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(attempts, 20)  # 20 par page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Options pour les filtres
        filter_options = {
            'statuses': WhatsAppMessageAttempt.objects.filter(
                source_app='agent_chine'
            ).values_list('status', flat=True).distinct(),
            'message_types': WhatsAppMessageAttempt.objects.filter(
                source_app='agent_chine'
            ).values_list('message_type', flat=True).distinct(),
            'categories': WhatsAppMessageAttempt.objects.filter(
                source_app='agent_chine'
            ).values_list('category', flat=True).distinct(),
        }
        
        context = {
            'app_name': 'Agent Chine',
            'source_app': 'agent_chine',
            'page_obj': page_obj,
            'filter_options': filter_options,
            'current_filters': {
                'status': status_filter,
                'message_type': message_type_filter,
                'category': category_filter,
                'search': search,
            }
        }
        
        return render(request, 'agent_chine_app/whatsapp_monitoring_list.html', context)
        
    except Exception as e:
        logger.error(f"Erreur liste monitoring agent_chine: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement de la liste: {str(e)}")
        return render(request, 'agent_chine_app/whatsapp_monitoring_list.html', {
            'app_name': 'Agent Chine',
            'source_app': 'agent_chine',
            'error': str(e)
        })


@login_required
def retry_failed_notifications(request):
    """
    Relance les notifications WhatsApp en échec pour agent_chine
    """
    if request.method == 'POST':
        try:
            # Traiter les retries pour agent_chine uniquement
            stats = WhatsAppMonitoringService.process_pending_retries(
                source_app='agent_chine',
                max_retries_per_run=50
            )
            
            messages.success(
                request, 
                f"Relance terminée pour Agent Chine: {stats['processed']} tentatives traitées, "
                f"{stats['success']} succès, {stats['failed']} échecs"
            )
            
            return JsonResponse({
                'success': True,
                'message': f"{stats['success']} notifications relancées avec succès",
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Erreur relance notifications agent_chine: {e}", exc_info=True)
            messages.error(request, f"Erreur lors de la relance: {str(e)}")
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def whatsapp_attempt_details(request, attempt_id):
    """
    Détails d'une tentative WhatsApp spécifique (si elle appartient à agent_chine)
    """
    try:
        attempt = WhatsAppMessageAttempt.objects.select_related('user').get(
            id=attempt_id,
            source_app='agent_chine'  # Sécurité: seulement agent_chine
        )
        
        context = {
            'app_name': 'Agent Chine',
            'source_app': 'agent_chine',
            'attempt': attempt,
        }
        
        return render(request, 'agent_chine_app/whatsapp_attempt_details.html', context)
        
    except WhatsAppMessageAttempt.DoesNotExist:
        messages.error(request, "Tentative non trouvée ou accès non autorisé")
        return redirect('agent_chine_app:whatsapp_monitoring_list')
    except Exception as e:
        logger.error(f"Erreur détails tentative {attempt_id}: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement: {str(e)}")
        return redirect('agent_chine_app:whatsapp_monitoring_list')


@login_required
def monitoring_stats_api(request):
    """
    API pour récupérer les stats de monitoring en temps réel pour agent_chine
    """
    try:
        # Stats pour agent_chine seulement
        agent_chine_attempts = WhatsAppMessageAttempt.objects.filter(source_app='agent_chine')
        
        stats = {
            'total': agent_chine_attempts.count(),
            'sent': agent_chine_attempts.filter(status='sent').count(),
            'failed': agent_chine_attempts.filter(status='failed').count(),
            'pending': agent_chine_attempts.filter(status='pending').count(),
            'retry': agent_chine_attempts.filter(status='retry').count(),
        }
        
        # Dernières tentatives (5 dernières)
        recent = list(agent_chine_attempts.select_related('user').order_by('-created_at')[:5].values(
            'id', 'user__telephone', 'message_type', 'status', 
            'created_at', 'title'
        ))
        
        # Convertir les dates en strings
        for item in recent:
            item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'recent_attempts': recent
        })
        
    except Exception as e:
        logger.error(f"Erreur API stats monitoring agent_chine: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)