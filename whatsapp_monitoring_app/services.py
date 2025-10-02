"""
Service centralisé de monitoring et retry pour les notifications WhatsApp
Utilisable par toutes les apps du projet
"""

import logging
from django.utils import timezone
from django.conf import settings
from django.db import models
from .models import WhatsAppMessageAttempt, WhatsAppWebhookLog
from notifications_app.wachap_service import wachap_service

logger = logging.getLogger(__name__)


class WhatsAppMonitoringService:
    """
    Service centralisé pour le monitoring et le retry des notifications WhatsApp
    Utilisable par toutes les apps (agent_chine, agent_mali, admin, etc.)
    """
    
    @staticmethod
    def create_message_attempt(user, message_content, source_app, message_type='notification', 
                             category='', title='', priority=3, max_attempts=3,
                             sender_role=None, region_override=None, context_data=None):
        """
        Crée une nouvelle tentative de message WhatsApp
        
        Args:
            user: Utilisateur destinataire
            message_content: Contenu du message
            source_app: App source ('agent_chine', 'agent_mali', 'admin_chine', etc.)
            message_type: Type de message
            category: Catégorie spécifique
            title: Titre du message
            priority: Priorité (1=très haute, 5=très basse)
            max_attempts: Nombre maximum de tentatives
            sender_role: Rôle de l'expéditeur
            region_override: Région forcée (chine/mali)
            context_data: Données contextuelles additionnelles
            
        Returns:
            WhatsAppMessageAttempt: Instance créée
        """
        attempt = WhatsAppMessageAttempt.objects.create(
            user=user,
            phone_number=user.telephone,
            source_app=source_app,
            message_type=message_type,
            category=category,
            priority=priority,
            title=title,
            message_content=message_content,
            max_attempts=max_attempts,
            sender_role=sender_role or getattr(user, 'role', None),
            region_override=region_override,
            context_data=context_data or {}
        )
        
        logger.info(f"Nouvelle tentative WhatsApp créée: {attempt.id} pour {user.telephone} depuis {source_app}")
        return attempt
    
    @staticmethod
    def send_message_attempt(attempt):
        """
        Tente d'envoyer un message WhatsApp et met à jour le statut
        
        Args:
            attempt: Instance WhatsAppMessageAttempt
            
        Returns:
            tuple: (success: bool, message_id: str|None, error_message: str|None)
        """
        try:
            # Marquer comme en cours d'envoi
            attempt.mark_as_sending()
            
            # Déterminer le numéro de destination avec redirection dev si nécessaire
            destination_phone = WhatsAppMonitoringService._get_destination_phone(
                original_phone=attempt.phone_number,
                user=attempt.user
            )
            
            # Enrichir le message en mode développement si nécessaire
            enriched_message = WhatsAppMonitoringService._enrich_message_for_dev(
                message=attempt.message_content,
                original_phone=attempt.phone_number,
                destination_phone=destination_phone,
                user=attempt.user,
                source_app=attempt.source_app
            )
            
            # Envoyer via WaChap
            success, result_message, message_id = wachap_service.send_message_with_type(
                phone=destination_phone,
                message=enriched_message,
                message_type=attempt.message_type,
                sender_role=attempt.sender_role,
                region=attempt.region_override
            )
            
            if success:
                # Marquer comme envoyé avec succès
                attempt.mark_as_sent(
                    provider_message_id=message_id,
                    provider_response={'result': result_message, 'timestamp': timezone.now().isoformat()}
                )
                
                logger.info(
                    f"WhatsApp envoyé avec succès - Attempt: {attempt.id}, "
                    f"To: {attempt.phone_number}, Via: {destination_phone}, "
                    f"Type: {attempt.message_type}, Source: {attempt.source_app}, Message ID: {message_id}"
                )
                
                return True, message_id, None
            else:
                # Marquer comme échoué avec possibilité de retry
                attempt.mark_as_failed(
                    error_message=result_message,
                    error_code='wachap_error'
                )
                
                logger.error(
                    f"Échec envoi WhatsApp - Attempt: {attempt.id}, "
                    f"To: {attempt.phone_number}, Source: {attempt.source_app}, Error: {result_message}"
                )
                
                return False, None, result_message
                
        except Exception as e:
            # Erreur technique, marquer comme échoué
            error_message = str(e)
            attempt.mark_as_failed(
                error_message=error_message,
                error_code='technical_error'
            )
            
            logger.error(
                f"Erreur technique envoi WhatsApp - Attempt: {attempt.id}, "
                f"To: {attempt.phone_number}, Source: {attempt.source_app}, Error: {error_message}"
            )
            
            return False, None, error_message
    
    @staticmethod
    def process_pending_retries(source_app=None, max_retries_per_run=50):
        """
        Traite les messages en attente de retry
        
        Args:
            source_app: Filtrer par app source (optionnel)
            max_retries_per_run: Nombre maximum de retries à traiter par exécution
            
        Returns:
            dict: Statistiques de traitement
        """
        stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        # Récupérer les messages prêts pour retry
        pending_attempts = WhatsAppMessageAttempt.get_pending_retries(source_app=source_app)[:max_retries_per_run]
        
        if source_app:
            logger.info(f"Traitement de {len(pending_attempts)} messages en attente de retry pour {source_app}")
        else:
            logger.info(f"Traitement de {len(pending_attempts)} messages en attente de retry (toutes apps)")
        
        for attempt in pending_attempts:
            try:
                stats['processed'] += 1
                
                success, message_id, error_message = WhatsAppMonitoringService.send_message_attempt(attempt)
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                stats['failed'] += 1
                error_msg = f"Erreur traitement retry attempt {attempt.id}: {str(e)}"
                stats['errors'].append(error_msg)
                logger.error(error_msg)
        
        if stats['processed'] > 0:
            source_info = f" pour {source_app}" if source_app else ""
            logger.info(
                f"Retry WhatsApp terminé{source_info} - Traité: {stats['processed']}, "
                f"Succès: {stats['success']}, Échecs: {stats['failed']}"
            )
        
        return stats
    
    @staticmethod
    def send_monitored_notification(user, message_content, source_app, message_type='notification',
                                  category='', title='', priority=3, max_attempts=3,
                                  send_immediately=True, **kwargs):
        """
        Interface principale pour envoyer une notification WhatsApp avec monitoring
        
        Args:
            user: Utilisateur destinataire
            message_content: Contenu du message
            source_app: App source ('agent_chine', 'agent_mali', etc.)
            message_type: Type de message
            category: Catégorie spécifique
            title: Titre du message
            priority: Priorité (1=très haute, 5=très basse)
            max_attempts: Nombre maximum de tentatives
            send_immediately: Si True, tente l'envoi immédiatement
            **kwargs: Paramètres additionnels (sender_role, region_override, context_data)
            
        Returns:
            tuple: (attempt: WhatsAppMessageAttempt, success: bool, error_message: str|None)
        """
        # Créer la tentative
        attempt = WhatsAppMonitoringService.create_message_attempt(
            user=user,
            message_content=message_content,
            source_app=source_app,
            message_type=message_type,
            category=category,
            title=title,
            priority=priority,
            max_attempts=max_attempts,
            sender_role=kwargs.get('sender_role'),
            region_override=kwargs.get('region_override'),
            context_data=kwargs.get('context_data')
        )
        
        if send_immediately:
            # Tenter l'envoi immédiatement
            success, message_id, error_message = WhatsAppMonitoringService.send_message_attempt(attempt)
            return attempt, success, error_message
        else:
            # Laisser en attente pour traitement ultérieur
            return attempt, False, "En attente de traitement"
    
    @staticmethod
    def cancel_pending_attempts(user=None, phone_number=None, category=None, source_app=None):
        """
        Annule des tentatives en attente selon les critères
        
        Args:
            user: Utilisateur (optionnel)
            phone_number: Numéro de téléphone (optionnel)
            category: Catégorie de messages (optionnel)
            source_app: App source (optionnel)
            
        Returns:
            int: Nombre de tentatives annulées
        """
        attempts = WhatsAppMessageAttempt.objects.filter(
            status__in=['pending', 'failed_retry']
        )
        
        if user:
            attempts = attempts.filter(user=user)
        if phone_number:
            attempts = attempts.filter(phone_number=phone_number)
        if category:
            attempts = attempts.filter(category=category)
        if source_app:
            attempts = attempts.filter(source_app=source_app)
        
        cancelled_count = 0
        for attempt in attempts:
            attempt.cancel()
            cancelled_count += 1
        
        logger.info(f"Annulé {cancelled_count} tentatives WhatsApp")
        return cancelled_count
    
    @staticmethod
    def get_monitoring_stats(source_app=None, days_back=7):
        """
        Retourne des statistiques de monitoring
        
        Args:
            source_app: Filtrer par app source (optionnel)
            days_back: Nombre de jours à analyser
            
        Returns:
            dict: Statistiques détaillées
        """
        stats = WhatsAppMessageAttempt.get_stats_summary(source_app=source_app, days_back=days_back)
        
        # Statistiques par type de message pour l'app spécifique
        queryset = WhatsAppMessageAttempt.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=days_back)
        )
        
        if source_app:
            queryset = queryset.filter(source_app=source_app)
        
        type_stats = queryset.values('message_type').annotate(
            count=models.Count('id'),
            sent_count=models.Count('id', filter=models.Q(status__in=['sent', 'delivered'])),
            failed_count=models.Count('id', filter=models.Q(status='failed_final'))
        ).order_by('-count')
        
        stats['by_type'] = list(type_stats)
        
        return stats
    
    @staticmethod
    def _get_destination_phone(original_phone, user=None):
        """
        Détermine le numéro de destination avec redirection dev si configurée
        """
        dev_mode = getattr(settings, 'DEBUG', False)
        admin_phone = getattr(settings, 'ADMIN_PHONE', '').strip()
        
        if dev_mode and admin_phone:
            return admin_phone
        return original_phone
    
    @staticmethod
    def _enrich_message_for_dev(message, original_phone, destination_phone, user=None, source_app=None):
        """
        Enrichit le message en mode développement avec les infos de redirection
        """
        if destination_phone != original_phone and user:
            return f"""[DEV] Message pour: {user.get_full_name()}
Tél réel: {original_phone}
Source: {source_app or 'Unknown'}

---
{message}
---
TS Air Cargo - Mode Développement"""
        return message
    
    @staticmethod
    def process_webhook(provider_message_id, webhook_type, status, raw_payload):
        """
        Traite un webhook reçu du provider WhatsApp
        
        Args:
            provider_message_id: ID du message chez le provider
            webhook_type: Type de webhook (status, delivery, read, etc.)
            status: Statut reporté
            raw_payload: Payload brute du webhook
            
        Returns:
            bool: True si le webhook a été traité avec succès
        """
        try:
            # Enregistrer le webhook
            webhook_log = WhatsAppWebhookLog.objects.create(
                provider_message_id=provider_message_id,
                webhook_type=webhook_type,
                status=status,
                raw_payload=raw_payload
            )
            
            # Trouver la tentative correspondante
            try:
                attempt = WhatsAppMessageAttempt.objects.get(
                    provider_message_id=provider_message_id
                )
                webhook_log.message_attempt = attempt
                webhook_log.save()
                
                # Mettre à jour le statut de la tentative selon le webhook
                if webhook_type == 'delivery' and status == 'delivered':
                    attempt.mark_as_delivered()
                elif webhook_type == 'read' and status == 'read':
                    attempt.status = 'read'
                    attempt.save()
                
                webhook_log.processed = True
                webhook_log.processed_at = timezone.now()
                webhook_log.save()
                
                logger.info(f"Webhook traité: {webhook_type} pour message {provider_message_id}")
                return True
                
            except WhatsAppMessageAttempt.DoesNotExist:
                # Tentative non trouvée, mais enregistrer le webhook quand même
                logger.warning(f"Tentative non trouvée pour message ID {provider_message_id}")
                return True
                
        except Exception as e:
            logger.error(f"Erreur traitement webhook: {str(e)}")
            return False


class WhatsAppRetryTask:
    """
    Tâche pour traiter les retries WhatsApp
    Cette classe peut être utilisée avec Celery ou Django-Q
    """
    
    @staticmethod
    def run_retry_task(source_app=None):
        """
        Exécute le traitement des retries pour une app spécifique ou toutes
        
        Args:
            source_app: App source à traiter (optionnel, traite toutes si None)
        """
        return WhatsAppMonitoringService.process_pending_retries(source_app=source_app)
    
    @staticmethod
    def cleanup_old_attempts(days_old=30):
        """
        Nettoie les anciennes tentatives pour éviter l'accumulation
        
        Args:
            days_old: Âge en jours des tentatives à supprimer
            
        Returns:
            int: Nombre de tentatives supprimées
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        # Supprimer seulement les tentatives finalisées anciennes
        deleted_count = WhatsAppMessageAttempt.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['sent', 'delivered', 'failed_final', 'cancelled']
        ).count()
        
        WhatsAppMessageAttempt.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['sent', 'delivered', 'failed_final', 'cancelled']
        ).delete()
        
        logger.info(f"Nettoyé {deleted_count} anciennes tentatives WhatsApp")
        return deleted_count


# Fonctions utilitaires pour faciliter l'utilisation depuis les autres apps

def send_whatsapp_monitored(user, message, source_app, **kwargs):
    """
    Fonction raccourcie pour envoyer une notification WhatsApp avec monitoring
    
    Usage:
        from whatsapp_monitoring_app.services import send_whatsapp_monitored
        
        attempt, success, error = send_whatsapp_monitored(
            user=user,
            message="Votre message",
            source_app='agent_chine',
            message_type='account',
            priority=1
        )
    """
    return WhatsAppMonitoringService.send_monitored_notification(
        user=user,
        message_content=message,
        source_app=source_app,
        **kwargs
    )

def get_app_stats(source_app, days_back=7):
    """
    Fonction raccourcie pour récupérer les stats d'une app
    
    Usage:
        from whatsapp_monitoring_app.services import get_app_stats
        
        stats = get_app_stats('agent_chine')
        print(f"Taux de succès: {stats['success_rate']}%")
    """
    return WhatsAppMonitoringService.get_monitoring_stats(source_app=source_app, days_back=days_back)

def process_app_retries(source_app):
    """
    Fonction raccourcie pour traiter les retries d'une app
    
    Usage:
        from whatsapp_monitoring_app.services import process_app_retries
        
        stats = process_app_retries('agent_chine')
        print(f"Traité: {stats['processed']}, Succès: {stats['success']}")
    """
    return WhatsAppMonitoringService.process_pending_retries(source_app=source_app)