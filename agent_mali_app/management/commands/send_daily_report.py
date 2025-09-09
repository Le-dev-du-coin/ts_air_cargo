"""
Commande Django pour l'envoi automatique des rapports journaliers via WhatsApp
Usage: python manage.py send_daily_report [--date YYYY-MM-DD]
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from datetime import datetime, date, timedelta
from agent_mali_app.views import generate_daily_report_pdf
from notifications_app.wachap_service import send_whatsapp_message
from django.conf import settings
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envoie automatiquement le rapport journalier aux administrateurs Mali via WhatsApp'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date pour le rapport (format YYYY-MM-DD). Par défaut: hier',
        )
        parser.add_argument(
            '--agent-id',
            type=int,
            help='ID de l\'agent Mali spécifique. Si non spécifié, utilise le premier agent Mali trouvé',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Mode test - affiche seulement les informations sans envoyer',
        )

    def handle(self, *args, **options):
        # Déterminer la date du rapport
        if options['date']:
            try:
                report_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Format de date invalide. Utilisez YYYY-MM-DD')
        else:
            # Par défaut, rapport d'hier
            report_date = date.today() - timedelta(days=1)

        self.stdout.write(f"📅 Génération du rapport pour le {report_date.strftime('%d/%m/%Y')}")

        # Trouver un agent Mali pour les statistiques
        if options['agent_id']:
            try:
                agent_mali = User.objects.get(id=options['agent_id'], is_agent_mali=True)
            except User.DoesNotExist:
                raise CommandError(f'Agent Mali avec ID {options["agent_id"]} non trouvé')
        else:
            # Prendre le premier agent Mali disponible
            agent_mali = User.objects.filter(is_agent_mali=True).first()
            if not agent_mali:
                raise CommandError('Aucun agent Mali trouvé dans le système')

        self.stdout.write(f"👤 Agent Mali: {agent_mali.get_full_name()} ({agent_mali.telephone})")

        try:
            # Générer le rapport PDF
            date_str = report_date.strftime('%Y-%m-%d')
            pdf_content = generate_daily_report_pdf(date_str)
            
            self.stdout.write(f"📄 Rapport PDF généré ({len(pdf_content)} bytes)")

            # Préparer le message WhatsApp
            message = f"""
📈 Rapport Journalier TS Air Cargo Mali

📅 Date: {report_date.strftime('%d/%m/%Y')}
👥 Agent: {agent_mali.get_full_name()}
🏢 Agence: Mali

📊 Rapport automatique quotidien généré à {datetime.now().strftime('%H:%M')}

Le rapport détaillé sera bientôt disponible en téléchargement.

Équipe TS Air Cargo Mali 🚀
            """.strip()

            # Numéro admin Mali - avec redirection de test
            if getattr(settings, 'DEBUG', False):
                # En mode développement, utiliser le numéro de test configuré
                admin_phone = '+22373451676'  # Votre numéro de test
                self.stdout.write(f"📱 Mode développement - Envoi vers: {admin_phone}")
            else:
                # En production, utiliser le vrai numéro admin Mali
                admin_phone = getattr(settings, 'MALI_ADMIN_PHONE', '+22312345678')
                self.stdout.write(f"📱 Mode production - Envoi vers: {admin_phone}")

            if options['test']:
                self.stdout.write("🧪 MODE TEST - Aucun message envoyé")
                self.stdout.write("Message qui serait envoyé:")
                self.stdout.write("-" * 50)
                self.stdout.write(message)
                self.stdout.write("-" * 50)
                self.stdout.write(self.style.SUCCESS("✅ Test terminé avec succès"))
                return

            # Envoyer le message WhatsApp via WaChap
            success = send_whatsapp_message(
                phone=admin_phone,
                message=message,
                sender_role='admin_mali'  # Rapport administratif
            )

            if success:
                self.stdout.write(self.style.SUCCESS("✅ Rapport journalier envoyé avec succès via WhatsApp"))
                logger.info(f"Rapport journalier {date_str} envoyé avec succès à {admin_phone}")
            else:
                self.stdout.write(self.style.ERROR("❌ Échec de l'envoi du rapport"))
                logger.error(f"Échec envoi rapport journalier {date_str} à {admin_phone}")

        except Exception as e:
            error_msg = f"Erreur lors de la génération/envoi du rapport: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            logger.error(error_msg)
            raise CommandError(error_msg)

        self.stdout.write(self.style.SUCCESS("🏁 Commande terminée"))
