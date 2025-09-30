"""
Commande Django pour traiter les messages WhatsApp en attente de retry
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from agent_chine_app.services.whatsapp_monitoring import WhatsAppMonitoringService, WhatsAppRetryTask
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Traite les messages WhatsApp en attente de retry'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-retries',
            type=int,
            default=50,
            help='Nombre maximum de messages à traiter par exécution (défaut: 50)'
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Nettoie également les anciennes tentatives'
        )
        
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=30,
            help='Âge en jours des tentatives à supprimer lors du nettoyage (défaut: 30)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans envoi réel de messages'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé des opérations'
        )
    
    def handle(self, *args, **options):
        start_time = timezone.now()
        
        self.stdout.write(
            self.style.SUCCESS(f'[{start_time}] Démarrage du traitement des retries WhatsApp')
        )
        
        try:
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING('Mode simulation activé - Aucun message ne sera envoyé')
                )
                stats = self._dry_run_stats(options['max_retries'])
            else:
                # Traitement normal des retries
                stats = WhatsAppMonitoringService.process_pending_retries(
                    max_retries_per_run=options['max_retries']
                )
            
            # Afficher les statistiques
            self._display_stats(stats, options['verbose'])
            
            # Nettoyage si demandé
            if options['cleanup']:
                self.stdout.write('\nNettoyage des anciennes tentatives...')
                deleted_count = WhatsAppRetryTask.cleanup_old_attempts(
                    days_old=options['cleanup_days']
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ {deleted_count} anciennes tentatives supprimées '
                        f'(plus de {options["cleanup_days"]} jours)'
                    )
                )
            
            # Durée totale
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[{end_time}] Traitement terminé en {duration:.2f} secondes'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors du traitement: {str(e)}')
            )
            logger.error(f"Erreur commande process_whatsapp_retries: {str(e)}")
            raise
    
    def _dry_run_stats(self, max_retries):
        """
        Simulation pour compter les messages qui seraient traités
        """
        from agent_chine_app.models.whatsapp_monitoring import WhatsAppMessageAttempt
        
        pending_attempts = WhatsAppMessageAttempt.get_pending_retries()[:max_retries]
        
        stats = {
            'processed': len(pending_attempts),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        if pending_attempts:
            self.stdout.write(f'Messages qui seraient traités:')
            for i, attempt in enumerate(pending_attempts[:10], 1):  # Afficher les 10 premiers
                self.stdout.write(
                    f'  {i}. {attempt.phone_number} - {attempt.get_message_type_display()} '
                    f'(tentative {attempt.attempt_count}/{attempt.max_attempts})'
                )
            
            if len(pending_attempts) > 10:
                self.stdout.write(f'  ... et {len(pending_attempts) - 10} autres')
        
        return stats
    
    def _display_stats(self, stats, verbose=False):
        """
        Affiche les statistiques de traitement
        """
        self.stdout.write('\n' + '='*50)
        self.stdout.write('STATISTIQUES DE TRAITEMENT')
        self.stdout.write('='*50)
        
        # Statistiques principales
        self.stdout.write(f'📊 Messages traités: {stats["processed"]}')
        
        if stats['processed'] > 0:
            success_rate = (stats['success'] / stats['processed']) * 100
            self.stdout.write(f'✅ Succès: {stats["success"]} ({success_rate:.1f}%)')
            self.stdout.write(f'❌ Échecs: {stats["failed"]}')
            
            # Détail des erreurs si verbose
            if verbose and stats['errors']:
                self.stdout.write('\nErreurs détaillées:')
                for error in stats['errors'][:10]:  # Limiter à 10 erreurs
                    self.stdout.write(f'  • {error}')
                
                if len(stats['errors']) > 10:
                    self.stdout.write(f'  ... et {len(stats["errors"]) - 10} autres erreurs')
        else:
            self.stdout.write('ℹ️  Aucun message en attente de retry')
        
        # Statistiques système si verbose
        if verbose:
            self._display_system_stats()
    
    def _display_system_stats(self):
        """
        Affiche des statistiques système détaillées
        """
        from agent_chine_app.models.whatsapp_monitoring import WhatsAppMessageAttempt
        
        self.stdout.write('\n' + '-'*30)
        self.stdout.write('ÉTAT DU SYSTÈME')
        self.stdout.write('-'*30)
        
        # Statistiques globales
        global_stats = WhatsAppMessageAttempt.get_stats_summary()
        
        self.stdout.write(f'Total des tentatives: {global_stats.get("total", 0)}')
        self.stdout.write(f'En attente: {global_stats.get("pending", 0)}')
        self.stdout.write(f'Envoyés: {global_stats.get("sent", 0)}')
        self.stdout.write(f'Livrés: {global_stats.get("delivered", 0)}')
        self.stdout.write(f'Échecs définitifs: {global_stats.get("failed_final", 0)}')
        self.stdout.write(f'En retry: {global_stats.get("failed_retry", 0)}')
        
        # Messages prêts pour le prochain retry
        now = timezone.now()
        ready_for_retry = WhatsAppMessageAttempt.objects.filter(
            status='failed_retry',
            next_retry_at__lte=now
        ).count()
        
        future_retries = WhatsAppMessageAttempt.objects.filter(
            status='failed_retry',
            next_retry_at__gt=now
        ).count()
        
        self.stdout.write(f'\nProchains retries:')
        self.stdout.write(f'  Prêts maintenant: {ready_for_retry}')
        self.stdout.write(f'  Programmés: {future_retries}')
        
        if future_retries > 0:
            # Prochain retry
            next_retry = WhatsAppMessageAttempt.objects.filter(
                status='failed_retry',
                next_retry_at__gt=now
            ).order_by('next_retry_at').first()
            
            if next_retry:
                time_until = next_retry.next_retry_at - now
                minutes_until = int(time_until.total_seconds() / 60)
                self.stdout.write(f'  Prochain retry dans: {minutes_until} minutes')


# Fonction utilitaire pour les cron jobs
def run_whatsapp_retries():
    """
    Fonction utilitaire pour exécuter le traitement depuis un cron job
    """
    try:
        stats = WhatsAppMonitoringService.process_pending_retries()
        logger.info(f"Cron WhatsApp retries: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Erreur cron WhatsApp retries: {str(e)}")
        raise