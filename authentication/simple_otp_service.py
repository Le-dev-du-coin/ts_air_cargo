"""
Service OTP simplifié et synchrone pour éliminer les timeouts et problèmes async
"""

from django.core.cache import cache
from django.utils import timezone
from notifications_app.wachap_service import send_whatsapp_otp
import logging
import random
import string

logger = logging.getLogger(__name__)

class SimpleOTPService:
    """Service OTP synchrone simple et fiable"""
    
    @staticmethod
    def generate_otp_code(length=6):
        """Génère un code OTP aléatoire"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def send_otp_sync(phone_number, user_id, role=None, timeout_seconds=600):
        """
        Envoie un OTP de manière synchrone
        
        Args:
            phone_number: Numéro de téléphone destinataire
            user_id: ID de l'utilisateur
            role: Rôle de l'utilisateur (optionnel)
            timeout_seconds: Durée de validité de l'OTP (défaut: 10 minutes)
            
        Returns:
            dict: Résultat de l'envoi avec succès/échec et message
        """
        try:
            # Générer le code OTP
            otp_code = SimpleOTPService.generate_otp_code()
            
            # Créer la clé cache simple
            cache_key = f"simple_otp_{phone_number}_{int(timezone.now().timestamp())}"
            
            logger.info(f"📤 Envoi OTP synchrone vers {phone_number} - Code: {'*' * len(otp_code)}")
            
            # Envoyer l'OTP via WaChap de manière synchrone
            success, message = send_whatsapp_otp(phone_number, otp_code)
            
            if success:
                # Stocker les données OTP en cache seulement si envoi réussi
                otp_data = {
                    'code': otp_code,
                    'user_id': user_id,
                    'phone_number': phone_number,
                    'role': role,
                    'created_at': timezone.now().isoformat(),
                    'sent_at': timezone.now().isoformat(),
                    'attempts': 0
                }
                
                # Sauvegarder en cache
                cache.set(cache_key, otp_data, timeout=timeout_seconds)
                
                logger.info(f"✅ OTP envoyé avec succès vers {phone_number}")
                
                return {
                    'success': True,
                    'cache_key': cache_key,
                    'user_message': f'Code de vérification envoyé avec succès. {message}',
                    'status': 'sent'
                }
            else:
                logger.error(f"❌ Échec envoi OTP vers {phone_number}: {message}")
                return {
                    'success': False,
                    'user_message': f'Erreur lors de l\'envoi du code: {message}',
                    'error': message
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur envoi OTP synchrone vers {phone_number}: {e}")
            return {
                'success': False,
                'user_message': 'Erreur technique lors de l\'envoi du code. Réessayez.',
                'error': str(e)
            }
    
    @staticmethod
    def verify_otp(cache_key, entered_code):
        """
        Vérifie un code OTP
        
        Args:
            cache_key: Clé cache de l'OTP
            entered_code: Code saisi par l'utilisateur
            
        Returns:
            dict: Résultat de la vérification
        """
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return {
                'success': False,
                'user_message': 'Code expiré ou invalide. Veuillez vous reconnecter.',
                'expired': True
            }
        
        stored_code = otp_data.get('code')
        user_id = otp_data.get('user_id')
        attempts = otp_data.get('attempts', 0)
        
        # Incrémenter les tentatives
        otp_data['attempts'] = attempts + 1
        cache.set(cache_key, otp_data, timeout=600)  # Renouveler le cache
        
        # Limiter les tentatives
        if attempts >= 5:
            cache.delete(cache_key)  # Supprimer après trop de tentatives
            return {
                'success': False,
                'user_message': 'Trop de tentatives. Veuillez vous reconnecter.',
                'expired': True
            }
        
        if entered_code == stored_code:
            # Code correct - nettoyer le cache
            cache.delete(cache_key)
            
            logger.info(f"✅ OTP vérifié avec succès pour utilisateur {user_id}")
            
            return {
                'success': True,
                'user_message': 'Code vérifié avec succès',
                'user_id': user_id,
                'user_data': otp_data
            }
        else:
            logger.warning(f"❌ Code OTP incorrect pour utilisateur {user_id} (tentative {attempts + 1})")
            
            return {
                'success': False,
                'user_message': f'Code incorrect. Il vous reste {5 - (attempts + 1)} tentatives.',
                'expired': False
            }
    
    @staticmethod
    def get_otp_info(cache_key):
        """
        Récupère les informations d'un OTP (sans le code)
        
        Args:
            cache_key: Clé cache de l'OTP
            
        Returns:
            dict: Informations de l'OTP
        """
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return {
                'found': False,
                'expired': True,
                'user_message': 'Session expirée.'
            }
        
        return {
            'found': True,
            'expired': False,
            'user_id': otp_data.get('user_id'),
            'phone_number': otp_data.get('phone_number'),
            'role': otp_data.get('role'),
            'attempts': otp_data.get('attempts', 0),
            'created_at': otp_data.get('created_at'),
            'sent_at': otp_data.get('sent_at'),
            'user_message': 'Code envoyé avec succès'
        }
    
    @staticmethod
    def resend_otp(cache_key):
        """
        Renvoie un OTP avec la même clé cache
        
        Args:
            cache_key: Clé cache de l'OTP existant
            
        Returns:
            dict: Résultat du renvoi
        """
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return {
                'success': False,
                'user_message': 'Session expirée. Veuillez vous reconnecter.'
            }
        
        phone_number = otp_data.get('phone_number')
        user_id = otp_data.get('user_id')
        role = otp_data.get('role')
        
        # Générer un nouveau code
        new_otp_code = SimpleOTPService.generate_otp_code()
        
        # Envoyer le nouveau code
        success, message = send_whatsapp_otp(phone_number, new_otp_code)
        
        if success:
            # Mettre à jour les données en cache
            otp_data['code'] = new_otp_code
            otp_data['sent_at'] = timezone.now().isoformat()
            otp_data['attempts'] = 0  # Réinitialiser les tentatives
            
            cache.set(cache_key, otp_data, timeout=600)
            
            logger.info(f"✅ OTP renvoyé avec succès vers {phone_number}")
            
            return {
                'success': True,
                'user_message': f'Code renvoyé avec succès. {message}'
            }
        else:
            logger.error(f"❌ Échec renvoi OTP vers {phone_number}: {message}")
            return {
                'success': False,
                'user_message': f'Erreur lors du renvoi: {message}'
            }
    
    @staticmethod
    def cleanup_expired_otps():
        """
        Nettoie les OTP expirés
        Note: Cette méthode n'est pas nécessaire avec le cache Django qui gère l'expiration automatiquement
        """
        # Le cache Django gère automatiquement l'expiration
        logger.info("Nettoyage automatique des OTP via cache Django")
        return True

# Fonction utilitaire pour la migration depuis l'ancien système
def migrate_from_async_to_sync():
    """
    Fonction utilitaire pour migrer depuis l'ancien système async vers le nouveau système sync
    """
    logger.info("Migration vers le système OTP synchrone - Nettoyage des anciennes clés...")
    
    # Note: Avec Django cache, impossible de lister les clés
    # Les anciennes clés expireront automatiquement
    
    return True