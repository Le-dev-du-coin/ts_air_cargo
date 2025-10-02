"""
Tâches Celery pour le monitoring WhatsApp
Permet l'envoi asynchrone des notifications
"""

import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from .services import WhatsAppMonitoringService, WhatsAppRetryTask
from .models import WhatsAppMessageAttempt

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_whatsapp_notification_async(self, user_id, message_content, source_app, 
                                   message_type='notification', category='', title='',
                                   priority=3, max_attempts=3, sender_role=None,
                                   region_override=None, context_data=None):
    """
    Tâche asynchrone pour envoyer une notification WhatsApp avec monitoring
    
    Args:
        user_id: ID de l'utilisateur destinataire
        message_content: Contenu du message
        source_app: App source
        message_type: Type de message
        category: Catégorie spécifique
        title: Titre du message
        priority: Priorité (1=très haute, 5=très basse)
        max_attempts: Nombre maximum de tentatives
        sender_role: Rôle de l'expéditeur
        region_override: Région forcée
        context_data: Données contextuelles
        
    Returns:
        dict: Résultat de l'envoi
    """
    try:
        # Récupérer l'utilisateur
        user = User.objects.get(id=user_id)
        
        # Ajouter info sur la tâche Celery dans context_data
        if context_data is None:
            context_data = {}
        context_data.update({
            'celery_task_id': self.request.id,
            'celery_retry': self.request.retries,
            'async_processing': True
        })
        
        # Créer la tentative de monitoring
        attempt = WhatsAppMonitoringService.create_message_attempt(
            user=user,
            message_content=message_content,
            source_app=source_app,
            message_type=message_type,
            category=category,
            title=title,
            priority=priority,
            max_attempts=max_attempts,
            sender_role=sender_role,
            region_override=region_override,
            context_data=context_data
        )
        
        # Tenter l'envoi immédiatement
        success, message_id, error_message = WhatsAppMonitoringService.send_message_attempt(attempt)
        
        result = {
            'attempt_id': attempt.id,
            'success': success,
            'message_id': message_id,
            'error_message': error_message,
            'user_phone': user.telephone,
            'source_app': source_app
        }
        
        if success:
            logger.info(f"✅ Notification WhatsApp async envoyée: {user.telephone} (attempt: {attempt.id})")
        else:
            logger.warning(f"⏳ Notification WhatsApp async en retry: {user.telephone} (attempt: {attempt.id}) - {error_message}")
        
        return result
        
    except User.DoesNotExist:
        error_msg = f"Utilisateur ID {user_id} non trouvé pour notification async"
        logger.error(error_msg)
        return {
            'success': False,
            'error_message': error_msg,
            'user_id': user_id
        }
        
    except Exception as e:
        error_msg = f"Erreur tâche async WhatsApp pour user {user_id}: {str(e)}"
        logger.error(error_msg)
        
        # Retry automatique en cas d'erreur
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry tâche async WhatsApp pour user {user_id} (tentative {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Délai exponentiel
        
        return {
            'success': False,
            'error_message': error_msg,
            'user_id': user_id,
            'retries_exhausted': True
        }


@shared_task(bind=True, max_retries=2)
def process_whatsapp_retries_task(self, source_app=None, max_retries_per_run=50):
    """
    Tâche Celery pour traiter les retries WhatsApp
    
    Args:
        source_app: App source à traiter (optionnel)
        max_retries_per_run: Nombre max de retries par exécution
        
    Returns:
        dict: Statistiques de traitement
    """
    try:
        logger.info(f"🚀 Début tâche Celery process_whatsapp_retries pour {source_app or 'toutes apps'}")
        
        stats = WhatsAppMonitoringService.process_pending_retries(
            source_app=source_app,
            max_retries_per_run=max_retries_per_run
        )
        
        # Ajouter des métadonnées
        stats.update({
            'celery_task_id': self.request.id,
            'processed_at': timezone.now().isoformat(),
            'source_app': source_app
        })
        
        logger.info(f"✅ Tâche Celery retries terminée: {stats['processed']} traités, {stats['success']} succès")
        return stats
        
    except Exception as e:
        error_msg = f"Erreur tâche Celery retries WhatsApp: {str(e)}"
        logger.error(error_msg)
        
        # Retry en cas d'erreur
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Retry dans 5 minutes
        
        return {
            'success': False,
            'error_message': error_msg,
            'celery_task_id': self.request.id
        }


@shared_task
def cleanup_old_whatsapp_attempts(days_old=30):
    """
    Tâche de nettoyage des anciennes tentatives WhatsApp
    
    Args:
        days_old: Âge en jours des tentatives à supprimer
        
    Returns:
        dict: Résultat du nettoyage
    """
    try:
        logger.info(f"🧹 Début nettoyage tentatives WhatsApp de plus de {days_old} jours")
        
        deleted_count = WhatsAppRetryTask.cleanup_old_attempts(days_old=days_old)
        
        result = {
            'success': True,
            'deleted_count': deleted_count,
            'days_old': days_old,
            'cleaned_at': timezone.now().isoformat()
        }
        
        logger.info(f"✅ Nettoyage terminé: {deleted_count} tentatives supprimées")
        return result
        
    except Exception as e:
        error_msg = f"Erreur nettoyage WhatsApp: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error_message': error_msg
        }


@shared_task
def send_bulk_whatsapp_notifications(notifications_data, source_app):
    """
    Tâche pour envoyer des notifications en masse
    
    Args:
        notifications_data: Liste de données de notifications
        source_app: App source
        
    Returns:
        dict: Statistiques d'envoi
    """
    try:
        stats = {
            'total': len(notifications_data),
            'processed': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for notification_data in notifications_data:
            try:
                # Lancer une tâche asynchrone pour chaque notification
                send_whatsapp_notification_async.delay(
                    user_id=notification_data['user_id'],
                    message_content=notification_data['message_content'],
                    source_app=source_app,
                    message_type=notification_data.get('message_type', 'notification'),
                    category=notification_data.get('category', ''),
                    title=notification_data.get('title', ''),
                    priority=notification_data.get('priority', 3),
                    max_attempts=notification_data.get('max_attempts', 3),
                    region_override=notification_data.get('region_override'),
                    context_data=notification_data.get('context_data')
                )
                stats['processed'] += 1
                stats['success'] += 1
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"User {notification_data.get('user_id')}: {str(e)}")
        
        logger.info(f"📤 Envoi en masse lancé: {stats['success']} notifications programmées")
        return stats
        
    except Exception as e:
        error_msg = f"Erreur envoi en masse WhatsApp: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error_message': error_msg
        }


# Fonction utilitaire pour envoyer une notification async facilement
def send_whatsapp_async(user, message_content, source_app, **kwargs):
    """
    Fonction utilitaire pour envoyer une notification WhatsApp de manière asynchrone
    
    Args:
        user: Utilisateur destinataire
        message_content: Contenu du message
        source_app: App source
        **kwargs: Paramètres additionnels
        
    Returns:
        AsyncResult: Objet Celery pour suivre la tâche
    """
    return send_whatsapp_notification_async.delay(
        user_id=user.id,
        message_content=message_content,
        source_app=source_app,
        message_type=kwargs.get('message_type', 'notification'),
        category=kwargs.get('category', ''),
        title=kwargs.get('title', ''),
        priority=kwargs.get('priority', 3),
        max_attempts=kwargs.get('max_attempts', 3),
        sender_role=kwargs.get('sender_role'),
        region_override=kwargs.get('region_override'),
        context_data=kwargs.get('context_data')
    )


# Configuration des tâches périodiques (pour Celery Beat)
# À ajouter dans settings.py si désiré :
"""
CELERY_BEAT_SCHEDULE = {
    'process-whatsapp-retries-every-5-minutes': {
        'task': 'whatsapp_monitoring_app.tasks.process_whatsapp_retries_task',
        'schedule': 300.0,  # 5 minutes
        'kwargs': {'max_retries_per_run': 100}
    },
    'cleanup-old-whatsapp-attempts-daily': {
        'task': 'whatsapp_monitoring_app.tasks.cleanup_old_whatsapp_attempts',
        'schedule': crontab(hour=2, minute=0),  # Tous les jours à 2h du matin
        'kwargs': {'days_old': 30}
    },
}
"""