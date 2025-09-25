"""
Service OTP asynchrone pour améliorer la robustesse et l'expérience utilisateur
Gère l'envoi d'OTP sans bloquer l'interface et avec retry automatique
"""

from django.core.cache import cache
from django.utils import timezone
from notifications_app.tasks import send_otp_async
import logging
import random
import string

logger = logging.getLogger(__name__)

class AsyncOTPService:
    """Service pour gérer l'envoi d'OTP de manière asynchrone"""
    
    @staticmethod
    def generate_otp_code(length=6):
        """Génère un code OTP aléatoire"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def send_otp_async(phone_number, user_id, role=None, extra_data=None):
        """
        Envoie un OTP de manière asynchrone
        
        Args:
            phone_number: Numéro de téléphone destinataire
            user_id: ID de l'utilisateur
            role: Rôle de l'utilisateur (optionnel)
            extra_data: Données supplémentaires à stocker (optionnel)
            
        Returns:
            dict: Statut de la demande avec clé cache pour suivi
        """
        try:
            # Générer le code OTP
            otp_code = AsyncOTPService.generate_otp_code()
            
            # Créer la clé cache unique
            cache_key = f"otp_async_{phone_number}_{int(timezone.now().timestamp())}"
            
            # Stocker les données OTP en cache avec statut initial
            otp_data = {
                'code': otp_code,
                'user_id': user_id,
                'phone_number': phone_number,
                'role': role,
                'status': 'pending',  # pending -> sending -> sent/failed/failed_final
                'created_at': timezone.now().isoformat(),
                'user_message': 'Envoi du code en cours...',
                'attempts': 0
            }
            
            # Ajouter les données extra si fournies
            if extra_data:
                otp_data.update(extra_data)
            
            # Sauvegarder en cache (10 minutes)
            cache.set(cache_key, otp_data, timeout=600)
            
            # Lancer la tâche asynchrone
            task_result = send_otp_async.delay(
                phone_number=phone_number,
                otp_code=otp_code,
                cache_key=cache_key,
                user_id=user_id
            )
            
            logger.info(f"📤 OTP asynchrone lancé pour {phone_number} - Cache: {cache_key} - Task: {task_result.id}")
            
            return {
                'success': True,
                'cache_key': cache_key,
                'task_id': task_result.id,
                'user_message': 'Envoi du code de vérification en cours...',
                'status': 'pending'
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur lancement OTP asynchrone pour {phone_number}: {e}")
            return {
                'success': False,
                'user_message': 'Erreur lors de la préparation de l\'envoi du code. Réessayez.',
                'error': str(e)
            }
    
    @staticmethod
    def get_otp_status(cache_key):
        """
        Récupère le statut actuel d'un OTP
        
        Args:
            cache_key: Clé cache de l'OTP
            
        Returns:
            dict: Statut et données de l'OTP
        """
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            return {
                'found': False,
                'expired': True,
                'user_message': 'Session expirée. Veuillez vous reconnecter.'
            }
        
        return {
            'found': True,
            'expired': False,
            'status': otp_data.get('status', 'pending'),
            'user_message': otp_data.get('user_message', 'Statut inconnu'),
            'code': otp_data.get('code'),
            'user_id': otp_data.get('user_id'),
            'phone_number': otp_data.get('phone_number'),
            'role': otp_data.get('role'),
            'attempts': otp_data.get('attempts', 0),
            'created_at': otp_data.get('created_at'),
            'completed_at': otp_data.get('completed_at')
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
                'user_message': 'Code expiré. Veuillez vous reconnecter.',
                'expired': True
            }
        
        stored_code = otp_data.get('code')
        user_id = otp_data.get('user_id')
        
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
            logger.warning(f"❌ Code OTP incorrect pour utilisateur {user_id}")
            
            return {
                'success': False,
                'user_message': 'Code incorrect. Vérifiez et réessayez.',
                'expired': False
            }
    
    @staticmethod
    def cleanup_expired_otps():
        """
        Nettoie les OTP expirés (à appeler périodiquement)
        Cette méthode peut être appelée par une tâche Celery planifiée
        """
        # Note: Django cache ne permet pas de lister toutes les clés
        # Cette méthode pourrait être implémentée avec Redis directement si nécessaire
        pass

# Fonctions utilitaires pour compatibilité
def send_otp_to_user(phone_number, user_id, role=None, **kwargs):
    """
    Fonction utilitaire pour envoyer un OTP à un utilisateur
    Compatible avec l'interface existante
    """
    return AsyncOTPService.send_otp_async(
        phone_number=phone_number,
        user_id=user_id,
        role=role,
        extra_data=kwargs
    )

def get_user_friendly_message(raw_message):
    """
    Convertit les messages techniques en messages compréhensibles
    """
    if not raw_message:
        return "Erreur inconnue"
    
    raw_lower = raw_message.lower()
    
    if "timeout" in raw_lower:
        return "Service temporairement indisponible. Veuillez patienter..."
    elif "invalid" in raw_lower or "invalidé" in raw_lower:
        return "Service en maintenance. Réessayez dans quelques minutes."
    elif "network" in raw_lower or "connexion" in raw_lower:
        return "Problème de connexion. Vérifiez votre connexion internet."
    elif "wachap" in raw_lower:
        return "Service de messagerie temporairement indisponible"
    else:
        return "Problème temporaire. Nos équipes travaillent à le résoudre."