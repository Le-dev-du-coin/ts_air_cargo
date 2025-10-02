"""
Intégration du monitoring WhatsApp centralisé dans agent_mali_app
Permet d'utiliser le système de monitoring avec des vues spécifiques à agent_mali
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
from whatsapp_monitoring_app.tasks import send_whatsapp_async
import logging

logger = logging.getLogger(__name__)


# =================== VUES DE MONITORING SPÉCIFIQUES À AGENT MALI ===================

@login_required
def whatsapp_monitoring_dashboard(request):
    """
    Dashboard de monitoring WhatsApp spécifique à agent_mali_app
    """
    try:
        # Filtrer uniquement les notifications de agent_mali
        agent_mali_attempts = WhatsAppMessageAttempt.objects.filter(source_app='agent_mali')
        
        # Statistiques générales pour agent_mali
        stats = {
            'total_attempts': agent_mali_attempts.count(),
            'successful': agent_mali_attempts.filter(status='sent').count(),
            'failed': agent_mali_attempts.filter(status='failed').count(),
            'pending': agent_mali_attempts.filter(status='pending').count(),
            'in_retry': agent_mali_attempts.filter(status='retry').count(),
        }
        
        # Calcul du taux de succès
        if stats['total_attempts'] > 0:
            stats['success_rate'] = round((stats['successful'] / stats['total_attempts']) * 100, 1)
        else:
            stats['success_rate'] = 0
        
        # Statistiques par type de message
        message_types = agent_mali_attempts.values('message_type').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Statistiques par catégorie
        categories = agent_mali_attempts.values('category').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='sent'))
        ).order_by('-count')
        
        # Dernières tentatives (limit 10)
        recent_attempts = agent_mali_attempts.select_related(
            'user'
        ).order_by('-created_at')[:10]
        
        # Notifications en échec qui nécessitent une attention
        failed_attempts = agent_mali_attempts.filter(
            status='failed',
            retry_count__gte=3
        ).select_related('user').order_by('-updated_at')[:5]
        
        context = {
            'app_name': 'Agent Mali',
            'source_app': 'agent_mali',
            'stats': stats,
            'message_types': message_types,
            'categories': categories,
            'recent_attempts': recent_attempts,
            'failed_attempts': failed_attempts,
        }
        
        return render(request, 'agent_mali_app/whatsapp_monitoring.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dashboard monitoring agent_mali: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement du monitoring: {str(e)}")
        return render(request, 'agent_mali_app/whatsapp_monitoring.html', {
            'app_name': 'Agent Mali',
            'source_app': 'agent_mali',
            'stats': {},
            'error': str(e)
        })


@login_required  
def whatsapp_monitoring_list(request):
    """
    Liste paginée des tentatives WhatsApp pour agent_mali_app
    """
    try:
        # Filtres
        status_filter = request.GET.get('status', '')
        message_type_filter = request.GET.get('message_type', '')
        category_filter = request.GET.get('category', '')
        search = request.GET.get('search', '')
        
        # Query de base pour agent_mali seulement
        attempts = WhatsAppMessageAttempt.objects.filter(
            source_app='agent_mali'
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
                source_app='agent_mali'
            ).values_list('status', flat=True).distinct(),
            'message_types': WhatsAppMessageAttempt.objects.filter(
                source_app='agent_mali'
            ).values_list('message_type', flat=True).distinct(),
            'categories': WhatsAppMessageAttempt.objects.filter(
                source_app='agent_mali'
            ).values_list('category', flat=True).distinct(),
        }
        
        context = {
            'app_name': 'Agent Mali',
            'source_app': 'agent_mali',
            'page_obj': page_obj,
            'filter_options': filter_options,
            'current_filters': {
                'status': status_filter,
                'message_type': message_type_filter,
                'category': category_filter,
                'search': search,
            }
        }
        
        return render(request, 'agent_mali_app/whatsapp_monitoring_list.html', context)
        
    except Exception as e:
        logger.error(f"Erreur liste monitoring agent_mali: {e}", exc_info=True)
        messages.error(request, f"Erreur lors du chargement de la liste: {str(e)}")
        return render(request, 'agent_mali_app/whatsapp_monitoring_list.html', {
            'app_name': 'Agent Mali',
            'source_app': 'agent_mali',
            'error': str(e)
        })


@login_required
def retry_failed_notifications(request):
    """
    Relance les notifications WhatsApp en échec pour agent_mali
    """
    if request.method == 'POST':
        try:
            # Traiter les retries pour agent_mali uniquement
            stats = WhatsAppMonitoringService.process_pending_retries(
                source_app='agent_mali',
                max_retries_per_run=50
            )
            
            messages.success(
                request, 
                f"Relance terminée pour Agent Mali: {stats['processed']} tentatives traitées, "
                f"{stats['success']} succès, {stats['failed']} échecs"
            )
            
            return JsonResponse({
                'success': True,
                'message': f"{stats['success']} notifications relancées avec succès",
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Erreur relance notifications agent_mali: {e}", exc_info=True)
            messages.error(request, f"Erreur lors de la relance: {str(e)}")
            
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# =================== FONCTIONS UTILITAIRES POUR AGENT MALI ===================

def send_whatsapp_notification_mali(user, message_content, message_type='notification', 
                                   category='', title='', priority=3, **kwargs):
    """
    Envoyer une notification WhatsApp depuis agent_mali_app avec monitoring automatique
    
    Args:
        user: Utilisateur destinataire
        message_content: Contenu du message
        message_type: Type de message
        category: Catégorie spécifique
        title: Titre du message
        priority: Priorité (1=très haute, 5=très basse)
        **kwargs: Paramètres additionnels
        
    Returns:
        AsyncResult: Tâche Celery pour suivre l'envoi
        
    Example:
        # Envoyer une notification de livraison
        task = send_whatsapp_notification_mali(
            user=client_user,
            message_content="Votre colis est arrivé au Mali!",
            message_type='delivery',
            category='colis_arrival',
            title='Arrivée colis',
            priority=2
        )
        
        print(f"Notification programmée: {task.id}")
    """
    try:
        # Utiliser la tâche Celery avec source_app='agent_mali'
        task_result = send_whatsapp_async(
            user=user,
            message_content=message_content,
            source_app='agent_mali',  # Important: identifier la source
            message_type=message_type,
            category=category,
            title=title,
            priority=priority,
            max_attempts=kwargs.get('max_attempts', 3),
            sender_role=kwargs.get('sender_role', 'agent_mali'),
            region_override=kwargs.get('region_override', 'mali'),
            context_data=kwargs.get('context_data', {})
        )
        
        logger.info(f"📤 Notification Agent Mali programmée: {user.telephone} (task: {task_result.id})")
        return task_result
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi notification Agent Mali pour {user.telephone}: {e}")
        raise


def send_bulk_notifications_mali(users_data, message_template, message_type='notification', **kwargs):
    """
    Envoyer des notifications en masse depuis agent_mali_app
    
    Args:
        users_data: Liste de données utilisateurs avec contenu personnalisé
        message_template: Template de message
        message_type: Type de message
        **kwargs: Paramètres additionnels
        
    Returns:
        list: Liste des tâches Celery lancées
        
    Example:
        users_data = [
            {
                'user': user1,
                'custom_content': 'Votre colis XYZ est arrivé'
            },
            {
                'user': user2, 
                'custom_content': 'Votre colis ABC est arrivé'
            }
        ]
        
        tasks = send_bulk_notifications_mali(
            users_data=users_data,
            message_template="📦 {custom_content} au Mali!",
            message_type='delivery'
        )
    """
    tasks = []
    
    try:
        for user_data in users_data:
            # Personnaliser le message
            message = message_template.format(**user_data)
            
            task = send_whatsapp_notification_mali(
                user=user_data['user'],
                message_content=message,
                message_type=message_type,
                **kwargs
            )
            tasks.append(task)
            
        logger.info(f"📤 {len(tasks)} notifications Agent Mali programmées en masse")
        return tasks
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi notifications en masse Agent Mali: {e}")
        raise


def get_mali_monitoring_stats():
    """
    Récupérer les statistiques de monitoring pour agent_mali
    
    Returns:
        dict: Statistiques complètes
    """
    try:
        agent_mali_attempts = WhatsAppMessageAttempt.objects.filter(source_app='agent_mali')
        
        stats = {
            'total_attempts': agent_mali_attempts.count(),
            'successful': agent_mali_attempts.filter(status='sent').count(),
            'failed': agent_mali_attempts.filter(status='failed').count(),
            'pending': agent_mali_attempts.filter(status='pending').count(),
            'in_retry': agent_mali_attempts.filter(status='retry').count(),
        }
        
        if stats['total_attempts'] > 0:
            stats['success_rate'] = round((stats['successful'] / stats['total_attempts']) * 100, 1)
        else:
            stats['success_rate'] = 0
        
        # Statistiques par période (dernières 24h, 7 jours, 30 jours)
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        
        stats['last_24h'] = agent_mali_attempts.filter(
            created_at__gte=now - timedelta(hours=24)
        ).count()
        
        stats['last_7days'] = agent_mali_attempts.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        
        stats['last_30days'] = agent_mali_attempts.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erreur stats monitoring Agent Mali: {e}")
        return {}


# =================== EXEMPLES D'UTILISATION ===================

"""
Exemples d'utilisation dans les vues de agent_mali_app:

1. Notification de livraison:
```python
from .whatsapp_integration import send_whatsapp_notification_mali

def notify_colis_delivered(colis):
    message = f"📦 Votre colis {colis.numero_suivi} est arrivé au Mali et prêt pour retrait!"
    
    task = send_whatsapp_notification_mali(
        user=colis.client.user,
        message_content=message,
        message_type='delivery',
        category='colis_arrival',
        title='Arrivée colis Mali',
        priority=2
    )
    
    return task
```

2. Notification de problème douane:
```python
def notify_customs_issue(colis):
    message = f"⚠️ Votre colis {colis.numero_suivi} nécessite des documents douaniers. Contactez notre bureau."
    
    task = send_whatsapp_notification_mali(
        user=colis.client.user,
        message_content=message,
        message_type='customs',
        category='customs_issue',
        title='Problème douane',
        priority=1  # Haute priorité
    )
    
    return task
```

3. Notification en masse d'arrivée de lot:
```python
def notify_lot_arrival(lot):
    users_data = []
    
    for colis in lot.colis.all():
        users_data.append({
            'user': colis.client.user,
            'numero_suivi': colis.numero_suivi,
            'custom_content': f"Colis {colis.numero_suivi}"
        })
    
    tasks = send_bulk_notifications_mali(
        users_data=users_data,
        message_template="📦 {custom_content} est arrivé au Mali! Lot: {lot_numero}",
        message_type='lot_arrival',
        category='lot_processing',
        lot_numero=lot.numero_lot
    )
    
    return tasks
```
"""