"""
Services de notifications pour ts_air_cargo
Version nettoyée - Migration WaChap complète
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Notification
from .wachap_service import wachap_service

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service centralisé pour l'envoi de notifications
    Migration complète vers WaChap - Twilio supprimé
    """
    
    @staticmethod
    def send_notification(user, message, method='whatsapp', title="Notification TS Air Cargo", categorie='information_generale'):
        """
        Envoie une notification à un utilisateur
        
        Args:
            user: Instance utilisateur
            message: Contenu du message
            method: Méthode d'envoi ('whatsapp', 'sms', 'email', 'in_app')
            title: Titre de la notification
            categorie: Catégorie de la notification
        """
        try:
            # Enregistrer la notification en base avec les bons champs
            notification = Notification.objects.create(
                destinataire=user,
                type_notification=method,
                categorie=categorie,
                titre=title,
                message=message,
                telephone_destinataire=user.telephone,
                email_destinataire=user.email or '',
                statut='en_attente'
            )
            
            # Envoyer selon la méthode choisie
            success = False
            message_id = None
            
            if method == 'whatsapp':
                success, message_id = NotificationService._send_whatsapp(user, message, categorie=categorie, title=title)
            elif method == 'sms':
                success, message_id = NotificationService._send_sms(user, message)
            elif method == 'email':
                success, message_id = NotificationService._send_email(user, message, title)
            elif method == 'in_app':
                success = True  # Déjà enregistré en base
            
            # Mettre à jour le statut de la notification
            if success:
                notification.marquer_comme_envoye(message_id)
                logger.info(f"Notification envoyée à {user.telephone} via {method}")
            else:
                notification.marquer_comme_echec("Échec d'envoi")
                logger.error(f"Échec envoi notification à {user.telephone} via {method}")
            
            return success
            
        except Exception as e:
            logger.error(f"Erreur envoi notification à {user.telephone}: {str(e)}")
            return False
    
    @staticmethod
    def _send_whatsapp(user, message, categorie=None, title=None):
        """
        Envoie un message WhatsApp via WaChap
        """
        try:
            # Déterminer le numéro de destination
            # En mode développement, rediriger UNIQUEMENT si ADMIN_PHONE est défini
            dev_mode = getattr(settings, 'DEBUG', False)
            admin_phone = getattr(settings, 'ADMIN_PHONE', '').strip()
            test_phone = admin_phone if (dev_mode and admin_phone) else None
            destination_phone = test_phone or user.telephone
            logger.debug(
                "WA DEBUG _send_whatsapp: original=%s destination=%s dev=%s admin_phone_set=%s categorie=%s title=%s",
                user.telephone,
                destination_phone,
                dev_mode,
                bool(admin_phone),
                categorie,
                title,
            )
            
            # Déterminer le rôle de l'expéditeur pour la sélection d'instance
            # Déterminer le type de message et le rôle expéditeur
            message_type = 'notification'
            if categorie in ['creation_compte', 'otp', 'system', 'information_systeme']:
                message_type = 'account' if categorie == 'creation_compte' else 'otp' if categorie == 'otp' else 'system'
            elif title and ('OTP' in title or 'Compte' in title or 'Système' in title):
                # fallback basé sur le titre
                if 'OTP' in title:
                    message_type = 'otp'
                elif 'Compte' in title:
                    message_type = 'account'
                elif 'Système' in title:
                    message_type = 'system'

            sender_role = 'system' if message_type in ['otp', 'account', 'system'] else getattr(user, 'role', None)
            
            # Enrichir le message en mode développement pour identification
            if test_phone and test_phone != user.telephone:
                enriched_message = f"""[DEV] Message pour: {user.get_full_name()}
Tél réel: {user.telephone}

---
{message}
---
TS Air Cargo - Mode Développement"""
            else:
                enriched_message = message
            
            # Envoyer via WaChap
            # Utiliser la version avec type pour router correctement les instances
            success, result_message, message_id = wachap_service.send_message_with_type(
                phone=destination_phone,
                message=enriched_message,
                message_type=message_type,
                sender_role=sender_role
            )
            
            if success:
                logger.info(
                    "WA OK: to_user=%s via=%s type=%s sender_role=%s msg_id=%s result=%s",
                    user.telephone,
                    destination_phone,
                    message_type,
                    sender_role,
                    message_id,
                    result_message,
                )
                return True, message_id
            else:
                logger.error(
                    "WA ERROR: to_user=%s via=%s type=%s sender_role=%s result=%s",
                    user.telephone,
                    destination_phone,
                    message_type,
                    sender_role,
                    result_message,
                )
                return False, None
                
        except Exception as e:
            logger.error(f"Erreur WhatsApp WaChap pour {user.telephone}: {str(e)}")
            return False, None
    
    @staticmethod
    def _send_sms(user, message):
        """
        Envoie un SMS (à implémenter avec un provider SMS)
        """
        # TODO: Intégrer avec un service SMS selon les besoins
        # Pour l'instant, simuler l'envoi (sans impression console)
        logger.info(f"SMS simulé à {user.telephone}: {message[:50]}...")
        return True, 'sms_simulation_id'
        
    @staticmethod
    def _send_email(user, message, title):
        """
        Envoie un email
        """
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ts-aircargo.com'),
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email envoyé à {user.email}")
            return True, 'email_sent'
        except Exception as e:
            logger.error(f"Erreur envoi email à {user.email}: {str(e)}")
            return False, None
    
    @staticmethod
    def send_client_creation_notification(user, temp_password):
        """
        Notification spécifique pour la création d'un compte client
        """
        # Message pour la création de compte
        message = f"""
🎉 Bienvenue chez TS Air Cargo !

👤 Nom: {user.get_full_name()}
📞 Téléphone: {user.telephone}
✉️ Email: {user.email}

🔑 Mot de passe temporaire: {temp_password}
⚠️ Veuillez changer ce mot de passe lors de votre première connexion.

🌐 Connectez-vous sur notre plateforme pour gérer vos envois.

Équipe TS Air Cargo 🚀
"""
        
        return NotificationService.send_notification(
            user=user,
            message=message,
            method='whatsapp',
            title='Création de compte TS Air Cargo',
            categorie='creation_compte'
        )
    
    @staticmethod
    def send_whatsapp_message(phone_number, message):
        """
        Interface simplifiée pour l'envoi de messages WhatsApp
        Compatible avec les anciennes interfaces
        
        Args:
            phone_number: Numéro de téléphone
            message: Message à envoyer
            
        Returns:
            bool: Succès de l'envoi
        """
        try:
            # Redirection vers numéro de test en mode développement (si ADMIN_PHONE défini)
            dev_mode = getattr(settings, 'DEBUG', False)
            admin_phone = getattr(settings, 'ADMIN_PHONE', '').strip()
            test_phone = admin_phone if (dev_mode and admin_phone) else None
            destination_phone = test_phone or phone_number
            
            # Message avec info de redirection si nécessaire
            if test_phone and test_phone != phone_number:
                enriched_message = f"""[DEV] Message pour: {phone_number}

{message}

TS Air Cargo - Mode Développement"""
            else:
                enriched_message = message
            
            # Envoyer via WaChap
            success, result_message, message_id = wachap_service.send_message(
                phone=destination_phone,
                message=enriched_message,
                sender_role=None  # Auto-détection
            )
            
            if success:
                logger.info(f"Message WhatsApp direct envoyé à {phone_number} (via {destination_phone})")
            else:
                logger.error(f"Erreur envoi WhatsApp direct à {phone_number}: {result_message}")
            
            return success
            
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp direct à {phone_number}: {str(e)}")
            return False
    
    @staticmethod
    def send_urgent_notification(user, message, title="🚨 Notification Urgente"):
        """
        Envoie une notification urgente avec formatage spécial
        """
        urgent_message = f"""🚨 URGENT - TS Air Cargo

{message}

⏰ {timezone.now().strftime('%d/%m/%Y à %H:%M')}
📞 Contactez-nous si nécessaire.

Équipe TS Air Cargo"""

        return NotificationService.send_notification(
            user=user,
            message=urgent_message,
            method='whatsapp',
            title=title,
            categorie='urgente'
        )
    
    @staticmethod
    def send_report_notification(recipient_phone, report_type, date, summary):
        """
        Envoie une notification de rapport automatique
        """
        message = f"""📊 Rapport {report_type} TS Air Cargo

📅 Date: {date}
📈 Résumé: {summary}

Le rapport détaillé est disponible sur la plateforme.

Équipe TS Air Cargo"""

        return NotificationService.send_whatsapp_message(recipient_phone, message)
    
    @staticmethod
    def send_lot_reception_notification(lot, agent_mali):
        """
        Envoie des notifications aux clients lors de la réception d'un lot au Mali
        
        Args:
            lot: Instance du lot réceptionné
            agent_mali: Agent qui a réceptionné le lot
            
        Returns:
            dict: Statistiques d'envoi
        """
        try:
            # Récupérer tous les clients uniques du lot
            colis_list = lot.colis.select_related('client__user').all()
            clients_notifies = set()  # Pour éviter les doublons
            notifications_envoyees = 0
            
            for colis in colis_list:
                client = colis.client
                
                # Éviter les doublons si un client a plusieurs colis dans le même lot
                if client.id in clients_notifies:
                    continue
                clients_notifies.add(client.id)
                
                # Préparer le message personnalisé
                message = f"""🇟🇲 Excellente nouvelle !

Votre colis du lot {lot.numero_lot} est arrivé à Bamako !

📅 Date d'arrivée: {timezone.now().strftime('%d/%m/%Y à %H:%M')}
📦 Numéro de suivi: {colis.numero_suivi}

Nous vous contacterons bientôt pour organiser la livraison.

Équipe TS Air Cargo Mali 🚀"""
                
                # Envoyer la notification
                success = NotificationService.send_notification(
                    user=client.user,
                    message=message,
                    method='whatsapp',
                    title='Colis arrivé au Mali',
                    categorie='colis_arrive'
                )
                
                if success:
                    notifications_envoyees += 1
            
            logger.info(f"Notifications d'arrivée envoyées pour le lot {lot.numero_lot}: {notifications_envoyees} clients notifiés")
            
            return {
                'success': True,
                'lot_id': lot.id,
                'clients_count': len(clients_notifies),
                'notifications_sent': notifications_envoyees
            }
            
        except Exception as e:
            error_msg = f"Erreur lors de l'envoi des notifications d'arrivée pour le lot {lot.numero_lot}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'lot_id': getattr(lot, 'id', None)
            }
