"""
Service de monitoring et retry pour les notifications WhatsApp
dans l'application agent_chine
"""

import logging
from django.utils import timezone
from django.conf import settings
from ..models.whatsapp_monitoring import WhatsAppMessageAttempt, WhatsAppWebhookLog
from notifications_app.wachap_service import wachap_service

logger = logging.getLogger(__name__)


class WhatsAppMonitoringService:
    """
    Service pour le monitoring et le retry des notifications WhatsApp
    """
    
    @staticmethod
    def create_message_attempt(user, message_content, message_type='notification', 
                             category='', title='', priority=3, max_attempts=3,
                             sender_role=None, region_override=None, context_data=None):
        """
        Crée une nouvelle tentative de message WhatsApp
        
        Args:
            user: Utilisateur destinataire
            message_content: Contenu du message
            message_type: Type de message ('account', 'otp', 'system', 'notification', etc.)
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
        
        logger.info(f"Nouvelle tentative WhatsApp créée: {attempt.id} pour {user.telephone}")
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
                user=attempt.user
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
                    f"Type: {attempt.message_type}, Message ID: {message_id}"
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
                    f"To: {attempt.phone_number}, Error: {result_message}"
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
                f"To: {attempt.phone_number}, Error: {error_message}"
            )
            
            return False, None, error_message
    
    @staticmethod
    def process_pending_retries(max_retries_per_run=50):
        """
        Traite les messages en attente de retry
        
        Args:
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
        pending_attempts = WhatsAppMessageAttempt.get_pending_retries()[:max_retries_per_run]
        
        logger.info(f"Traitement de {len(pending_attempts)} messages en attente de retry")
        
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
            logger.info(
                f"Retry WhatsApp terminé - Traité: {stats['processed']}, "
                f"Succès: {stats['success']}, Échecs: {stats['failed']}"
            )
        
        return stats
    
    @staticmethod
    def send_monitored_notification(user, message_content, message_type='notification',
                                  category='', title='', priority=3, max_attempts=3,
                                  send_immediately=True, **kwargs):
        """
        Interface principale pour envoyer une notification WhatsApp avec monitoring
        
        Args:
            user: Utilisateur destinataire
            message_content: Contenu du message
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
    def cancel_pending_attempts(user=None, phone_number=None, category=None):
        """
        Annule des tentatives en attente selon les critères
        
        Args:
            user: Utilisateur (optionnel)
            phone_number: Numéro de téléphone (optionnel)
            category: Catégorie de messages (optionnel)
            
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
        
        cancelled_count = 0
        for attempt in attempts:
            attempt.cancel()
            cancelled_count += 1
        
        logger.info(f"Annulé {cancelled_count} tentatives WhatsApp")
        return cancelled_count
    
    @staticmethod
    def get_monitoring_stats(days_back=7):
        """
        Retourne des statistiques de monitoring
        
        Args:
            days_back: Nombre de jours à analyser
            
        Returns:
            dict: Statistiques détaillées
        """
        from django.db.models import Count, Q, Avg
        from django.utils import timezone
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days_back)
        
        recent_attempts = WhatsAppMessageAttempt.objects.filter(
            created_at__gte=cutoff_date
        )
        
        stats = recent_attempts.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            sending=Count('id', filter=Q(status='sending')),
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            failed_retry=Count('id', filter=Q(status='failed_retry')),
            failed_final=Count('id', filter=Q(status='failed_final')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            avg_attempts=Avg('attempt_count')
        )
        
        # Calculer les taux
        if stats['total'] > 0:
            stats['success_rate'] = ((stats['sent'] + stats['delivered']) / stats['total']) * 100
            stats['failure_rate'] = (stats['failed_final'] / stats['total']) * 100
            stats['pending_rate'] = ((stats['pending'] + stats['failed_retry']) / stats['total']) * 100
        else:
            stats['success_rate'] = 0
            stats['failure_rate'] = 0
            stats['pending_rate'] = 0
        
        # Statistiques par type de message
        type_stats = recent_attempts.values('message_type').annotate(
            count=Count('id'),
            sent_count=Count('id', filter=Q(status__in=['sent', 'delivered'])),
            failed_count=Count('id', filter=Q(status='failed_final'))
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
    def _enrich_message_for_dev(message, original_phone, destination_phone, user=None):
        """
        Enrichit le message en mode développement avec les infos de redirection
        """
        if destination_phone != original_phone and user:
            return f"""[DEV] Message pour: {user.get_full_name()}
Tél réel: {original_phone}

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
    def run_retry_task():
        """
        Exécute le traitement des retries
        Peut être appelé par un cron job ou une tâche périodique
        """
        return WhatsAppMonitoringService.process_pending_retries()
    
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