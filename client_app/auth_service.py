from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.utils import timezone
from .models import Client, OTPVerification
from notifications_app.services import NotificationService
import logging

logger = logging.getLogger(__name__)


class ClientAuthService:
    """Service d'authentification client avec OTP WhatsApp"""
    
    @staticmethod
    def initiate_registration(telephone, nom_complet, adresse=None, ville=None):
        """Initie l'inscription d'un client avec envoi d'OTP"""
        try:
            # Vérifier si le téléphone existe déjà
            if Client.objects.filter(telephone=telephone).exists():
                return {
                    'success': False,
                    'error': 'Un compte existe déjà avec ce numéro de téléphone'
                }
            
            # Générer et sauvegarder l'OTP
            otp_code = OTPVerification.generate_otp()
            
            # Supprimer les anciens OTP non utilisés pour ce numéro
            OTPVerification.objects.filter(telephone=telephone, is_used=False).delete()
            
            # Créer le nouvel OTP
            otp_verification = OTPVerification.objects.create(
                telephone=telephone,
                otp_code=otp_code
            )
            
            # Envoyer l'OTP par WhatsApp
            notification_service = NotificationService()
            message = f"🔐 Code de vérification TS Air Cargo: {otp_code}\\n\\nUtilisez ce code pour finaliser votre inscription.\\n\\n⏰ Ce code expire dans 5 minutes."
            
            whatsapp_result = notification_service.send_whatsapp_message(
                to=telephone,
                message=message
            )
            
            if not whatsapp_result.get('success'):
                logger.error(f"Échec envoi OTP WhatsApp pour {telephone}: {whatsapp_result.get('error')}")
                return {
                    'success': False,
                    'error': 'Erreur lors de l\'envoi du code de vérification'
                }
            
            return {
                'success': True,
                'message': 'Code de vérification envoyé par WhatsApp',
                'telephone': telephone
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initiation d'inscription: {str(e)}")
            return {
                'success': False,
                'error': 'Une erreur s\'est produite. Veuillez réessayer.'
            }
    
    @staticmethod
    def verify_otp_and_register(telephone, otp_code, nom_complet, adresse=None, ville=None):
        """Vérifie l'OTP et finalise l'inscription"""
        try:
            # Vérifier l'OTP
            otp_verification = OTPVerification.objects.filter(
                telephone=telephone,
                otp_code=otp_code,
                is_used=False
            ).first()
            
            if not otp_verification:
                return {
                    'success': False,
                    'error': 'Code de vérification invalide'
                }
            
            if otp_verification.is_expired():
                return {
                    'success': False,
                    'error': 'Code de vérification expiré'
                }
            
            # Marquer l'OTP comme utilisé
            otp_verification.is_used = True
            otp_verification.save()
            
            # Créer l'utilisateur Django
            username = f"client_{telephone}"
            user = User.objects.create_user(
                username=username,
                first_name=nom_complet.split()[0] if nom_complet else '',
                last_name=' '.join(nom_complet.split()[1:]) if len(nom_complet.split()) > 1 else '',
                is_active=True
            )
            
            # Créer le profil client
            client = Client.objects.create(
                user=user,
                telephone=telephone,
                nom_complet=nom_complet,
                adresse=adresse or '',
                ville=ville or '',
                is_verified=True
            )
            
            logger.info(f"Nouveau client inscrit: {nom_complet} ({telephone})")
            
            return {
                'success': True,
                'message': 'Inscription réussie ! Vous pouvez maintenant vous connecter.',
                'client': client
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP: {str(e)}")
            return {
                'success': False,
                'error': 'Une erreur s\'est produite lors de l\'inscription'
            }
    
    @staticmethod
    def initiate_login(telephone):
        """Initie la connexion avec envoi d'OTP"""
        try:
            # Vérifier si le client existe
            client = Client.objects.filter(telephone=telephone, is_verified=True).first()
            if not client:
                return {
                    'success': False,
                    'error': 'Aucun compte trouvé avec ce numéro de téléphone'
                }
            
            # Générer et sauvegarder l'OTP
            otp_code = OTPVerification.generate_otp()
            
            # Supprimer les anciens OTP non utilisés pour ce numéro
            OTPVerification.objects.filter(telephone=telephone, is_used=False).delete()
            
            # Créer le nouvel OTP
            otp_verification = OTPVerification.objects.create(
                telephone=telephone,
                otp_code=otp_code
            )
            
            # Envoyer l'OTP par WhatsApp
            notification_service = NotificationService()
            message = f"🔐 Code de connexion TS Air Cargo: {otp_code}\\n\\nBonjour {client.nom_complet}, utilisez ce code pour vous connecter.\\n\\n⏰ Ce code expire dans 5 minutes."
            
            whatsapp_result = notification_service.send_whatsapp_message(
                to=telephone,
                message=message
            )
            
            if not whatsapp_result.get('success'):
                logger.error(f"Échec envoi OTP WhatsApp pour connexion {telephone}: {whatsapp_result.get('error')}")
                return {
                    'success': False,
                    'error': 'Erreur lors de l\'envoi du code de vérification'
                }
            
            return {
                'success': True,
                'message': 'Code de vérification envoyé par WhatsApp',
                'telephone': telephone
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initiation de connexion: {str(e)}")
            return {
                'success': False,
                'error': 'Une erreur s\'est produite. Veuillez réessayer.'
            }
    
    @staticmethod
    def verify_otp_and_login(request, telephone, otp_code):
        """Vérifie l'OTP et connecte l'utilisateur"""
        try:
            # Vérifier l'OTP
            otp_verification = OTPVerification.objects.filter(
                telephone=telephone,
                otp_code=otp_code,
                is_used=False
            ).first()
            
            if not otp_verification:
                return {
                    'success': False,
                    'error': 'Code de vérification invalide'
                }
            
            if otp_verification.is_expired():
                return {
                    'success': False,
                    'error': 'Code de vérification expiré'
                }
            
            # Récupérer le client
            client = Client.objects.filter(telephone=telephone, is_verified=True).first()
            if not client:
                return {
                    'success': False,
                    'error': 'Compte client introuvable'
                }
            
            # Marquer l'OTP comme utilisé
            otp_verification.is_used = True
            otp_verification.save()
            
            # Connecter l'utilisateur
            login(request, client.user)
            
            logger.info(f"Client connecté: {client.nom_complet} ({telephone})")
            
            return {
                'success': True,
                'message': 'Connexion réussie !',
                'client': client
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP connexion: {str(e)}")
            return {
                'success': False,
                'error': 'Une erreur s\'est produite lors de la connexion'
            }
