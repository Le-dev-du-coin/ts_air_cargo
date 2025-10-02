"""
Commande Django centralisée pour traiter les messages WhatsApp en attente de retry
Utilisable pour toutes les apps ou pour une app spécifique
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from whatsapp_monitoring_app.services import WhatsAppMonitoringService, WhatsAppRetryTask
from whatsapp_monitoring_app.models import WhatsAppMessageAttempt
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Traite les messages WhatsApp en attente de retry (toutes apps ou app spécifique)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--source-app',
            type=str,
            help='Filtrer par app source (agent_chine, agent_mali, admin_chine, admin_mali, etc.)'
        )
        
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
        
        parser.add_argument(
            '--list-apps',
            action='store_true',
            help='Affiche les statistiques par app source'
        )
    
    def handle(self, *args, **options):
        start_time = timezone.now()
        
        if options['list_apps']:
            self._list_app_stats()
            return
        
        source_app = options['source_app']
        
        if source_app:
            self.stdout.write(
                self.style.SUCCESS(f'[{start_time}] Démarrage du traitement des retries WhatsApp pour {source_app}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'[{start_time}] Démarrage du traitement des retries WhatsApp (toutes apps)')
            )
        
        try:
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING('Mode simulation activé - Aucun message ne sera envoyé')
                )
                stats = self._dry_run_stats(options['max_retries'], source_app)
            else:
                # Traitement normal des retries
                stats = WhatsAppMonitoringService.process_pending_retries(
                    source_app=source_app,
                    max_retries_per_run=options['max_retries']
                )
            
            # Afficher les statistiques
            self._display_stats(stats, options['verbose'], source_app)
            
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
    
    def _list_app_stats(self):
        """
        Affiche les statistiques par app source
        """
        self.stdout.write(self.style.SUCCESS('📊 STATISTIQUES PAR APP SOURCE'))
        self.stdout.write('='*60)
        
        # Récupérer toutes les apps sources avec des tentatives
        app_sources = WhatsAppMessageAttempt.objects.values_list('source_app', flat=True).distinct()
        
        for app_source in sorted(app_sources):
            stats = WhatsAppMonitoringService.get_monitoring_stats(source_app=app_source, days_back=7)
            
            self.stdout.write(f'\n🔹 {app_source.upper()}:')
            self.stdout.write(f'   Total (7j): {stats.get("total", 0)}')
            self.stdout.write(f'   Succès: {stats.get("sent", 0) + stats.get("delivered", 0)} ({stats.get("success_rate", 0):.1f}%)')
            self.stdout.write(f'   En retry: {stats.get("failed_retry", 0)}')
            self.stdout.write(f'   Échecs définitifs: {stats.get("failed_final", 0)}')
        
        # Messages prêts pour retry maintenant par app
        self.stdout.write('\n🔄 MESSAGES PRÊTS POUR RETRY:')
        for app_source in sorted(app_sources):
            ready_count = WhatsAppMessageAttempt.get_pending_retries(source_app=app_source).count()
            if ready_count > 0:
                self.stdout.write(f'   {app_source}: {ready_count} messages')
    
    def _dry_run_stats(self, max_retries, source_app=None):
        """
        Simulation pour compter les messages qui seraient traités
        """
        pending_attempts = WhatsAppMessageAttempt.get_pending_retries(source_app=source_app)[:max_retries]
        
        stats = {
            'processed': len(pending_attempts),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        if pending_attempts:
            app_filter = f" pour {source_app}" if source_app else ""
            self.stdout.write(f'Messages qui seraient traités{app_filter}:')
            
            # Grouper par source_app pour l'affichage
            from collections import defaultdict
            apps_count = defaultdict(int)
            
            for i, attempt in enumerate(pending_attempts[:10], 1):  # Afficher les 10 premiers
                self.stdout.write(
                    f'  {i}. [{attempt.source_app}] {attempt.phone_number} - {attempt.get_message_type_display()} '
                    f'(tentative {attempt.attempt_count}/{attempt.max_attempts})'
                )
                apps_count[attempt.source_app] += 1
            
            if len(pending_attempts) > 10:
                self.stdout.write(f'  ... et {len(pending_attempts) - 10} autres')
            
            # Résumé par app
            if len(apps_count) > 1:
                self.stdout.write('\nRépartition par app:')
                for app, count in sorted(apps_count.items()):
                    self.stdout.write(f'  {app}: {count} messages')
        
        return stats
    
    def _display_stats(self, stats, verbose=False, source_app=None):
        """
        Affiche les statistiques de traitement
        """
        self.stdout.write('\n' + '='*50)
        if source_app:
            self.stdout.write(f'STATISTIQUES DE TRAITEMENT - {source_app.upper()}')
        else:
            self.stdout.write('STATISTIQUES DE TRAITEMENT - TOUTES APPS')
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
            self._display_system_stats(source_app)
    
    def _display_system_stats(self, source_app=None):
        """
        Affiche des statistiques système détaillées
        """
        self.stdout.write('\n' + '-'*30)
        if source_app:
            self.stdout.write(f'ÉTAT DU SYSTÈME - {source_app.upper()}')
        else:
            self.stdout.write('ÉTAT DU SYSTÈME - GLOBAL')
        self.stdout.write('-'*30)
        
        # Statistiques globales
        stats = WhatsAppMonitoringService.get_monitoring_stats(source_app=source_app, days_back=7)
        
        self.stdout.write(f'Total des tentatives (7j): {stats.get("total", 0)}')
        self.stdout.write(f'En attente: {stats.get("pending", 0)}')
        self.stdout.write(f'Envoyés: {stats.get("sent", 0)}')
        self.stdout.write(f'Livrés: {stats.get("delivered", 0)}')
        self.stdout.write(f'Échecs définitifs: {stats.get("failed_final", 0)}')
        self.stdout.write(f'En retry: {stats.get("failed_retry", 0)}')
        
        # Messages prêts pour le prochain retry
        now = timezone.now()
        ready_for_retry = WhatsAppMessageAttempt.get_pending_retries(source_app=source_app).count()
        
        future_retries_query = WhatsAppMessageAttempt.objects.filter(
            status='failed_retry',
            next_retry_at__gt=now
        )
        if source_app:
            future_retries_query = future_retries_query.filter(source_app=source_app)
        future_retries = future_retries_query.count()
        
        self.stdout.write(f'\nProchains retries:')
        self.stdout.write(f'  Prêts maintenant: {ready_for_retry}')
        self.stdout.write(f'  Programmés: {future_retries}')
        
        if future_retries > 0:
            # Prochain retry
            next_retry = future_retries_query.order_by('next_retry_at').first()
            
            if next_retry:
                time_until = next_retry.next_retry_at - now
                minutes_until = int(time_until.total_seconds() / 60)
                self.stdout.write(f'  Prochain retry dans: {minutes_until} minutes')
        
        # Statistiques par type de message si pas de filtre app
        if not source_app and stats.get('by_type'):
            self.stdout.write(f'\nPar type de message:')
            for type_stat in stats['by_type'][:5]:  # Top 5
                self.stdout.write(
                    f"  {type_stat['message_type']}: {type_stat['count']} "
                    f"(succès: {type_stat['sent_count']})"
                )


# Fonctions utilitaires pour les cron jobs
def run_whatsapp_retries(source_app=None):
    """
    Fonction utilitaire pour exécuter le traitement depuis un cron job
    
    Args:
        source_app: App source à traiter (optionnel)
    """
    try:
        stats = WhatsAppMonitoringService.process_pending_retries(source_app=source_app)
        if source_app:
            logger.info(f"Cron WhatsApp retries pour {source_app}: {stats}")
        else:
            logger.info(f"Cron WhatsApp retries (global): {stats}")
        return stats
    except Exception as e:
        logger.error(f"Erreur cron WhatsApp retries: {str(e)}")
        raise

def run_app_specific_retries():
    """
    Fonction pour traiter les retries de chaque app séparément
    Utile pour distribuer la charge
    """
    app_sources = WhatsAppMessageAttempt.objects.values_list('source_app', flat=True).distinct()
    results = {}
    
    for app_source in app_sources:
        try:
            stats = run_whatsapp_retries(source_app=app_source)
            results[app_source] = stats
        except Exception as e:
            results[app_source] = {'error': str(e)}
            logger.error(f"Erreur retry pour {app_source}: {str(e)}")
    
    return results