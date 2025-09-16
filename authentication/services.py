"""
Services d'authentification pour ts_air_cargo
"""

import secrets
import string
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string

User = get_user_model()

class UserCreationService:
    """
    Service pour gérer la création automatique des comptes utilisateurs
    """
    
    @staticmethod
    def generate_temp_password(length=8):
        """
        Génère un mot de passe temporaire sécurisé
        """
        characters = string.ascii_letters + string.digits
        # Assurer au moins une majuscule, une minuscule et un chiffre
        password = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase), 
            secrets.choice(string.digits),
        ]
        
        # Compléter avec des caractères aléatoires
        for _ in range(length - 3):
            password.append(secrets.choice(characters))
        
        # Mélanger la liste
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)
    
    @staticmethod
    def create_client_account(telephone, first_name, last_name, email=None):
        """
        Crée automatiquement un compte client avec un mot de passe temporaire
        
        Args:
            telephone (str): Numéro de téléphone (identifiant unique)
            first_name (str): Prénom du client
            last_name (str): Nom du client
            email (str, optional): Email du client
            
        Returns:
            dict: {
                'user': User instance,
                'password': mot de passe temporaire généré,
                'created': True si nouveau compte, False si existant
            }
        """
        try:
            # Vérifier si l'utilisateur existe déjà
            user = User.objects.get(telephone=telephone)
            return {
                'user': user,
                'password': None,  # Pas de nouveau mot de passe
                'created': False
            }
        except User.DoesNotExist:
            # Créer un nouveau compte
            temp_password = UserCreationService.generate_temp_password()
            
            user = User.objects.create_user(
                telephone=telephone,
                first_name=first_name,
                last_name=last_name,
                email=email or f"{telephone}@temp.ts-cargo.com",
                password=temp_password,
                role='client',
                is_client=True
            )
            
            return {
                'user': user,
                'password': temp_password,
                'created': True
            }
    
    @staticmethod
    def send_credentials_notification(user, temp_password, method='whatsapp'):
        """
        Envoie les identifiants de connexion au client
        
        Args:
            user: Instance utilisateur
            temp_password: Mot de passe temporaire
            method: Méthode d'envoi ('sms', 'whatsapp', 'email')
        """
        from notifications_app.services import NotificationService
        
        message = f"""
Bonjour {user.get_full_name()},

Votre compte TS Air Cargo a été créé.

Identifiants de connexion:
- Téléphone: {user.telephone}
- Mot de passe temporaire: {temp_password}

Important:
- Connectez-vous et changez votre mot de passe dès que possible.
- Ce mot de passe temporaire expire rapidement pour des raisons de sécurité.

Lien de connexion: https://ts-aircargo.com/login

TS Air Cargo
"""
        
        # Utiliser le service de notifications
        NotificationService.send_notification(
            user=user,
            message=message,
            method=method,
            title="Création de compte TS Air Cargo",
            categorie='creation_compte'
        )

class PasswordResetService:
    """
    Service pour la réinitialisation de mots de passe
    """
    
    @staticmethod
    def generate_reset_token():
        """
        Génère un token de réinitialisation sécurisé
        """
        return get_random_string(32)
    
    @staticmethod
    def create_reset_token(user):
        """
        Crée un token de réinitialisation pour un utilisateur
        """
        from .models import PasswordResetToken
        
        # Supprimer les anciens tokens
        PasswordResetToken.objects.filter(user=user).delete()
        
        # Créer un nouveau token
        token = PasswordResetService.generate_reset_token()
        reset_token = PasswordResetToken.objects.create(
            user=user,
            token=token
        )
        
        return reset_token
    
    @staticmethod
    def send_reset_notification(user, reset_token):
        """
        Envoie un lien de réinitialisation de mot de passe
        """
        from notifications_app.services import NotificationService
        
        reset_link = f"https://ts-cargo.com/password/reset/confirm/{reset_token.token}/"
        
        message = f"""
        Bonjour {user.get_full_name()},
        
        Une demande de réinitialisation de mot de passe a été effectuée.
        
        🔗 Cliquez sur le lien pour créer un nouveau mot de passe :
        {reset_link}
        
        ⏱️ Ce lien expire dans 24h.
        
        Si vous n'avez pas demandé cette réinitialisation, ignorez ce message.
        
        Équipe TS Air Cargo
        """
        
        NotificationService.send_notification(
            user=user,
            message=message,
            method='whatsapp',  # Priorité WhatsApp selon DEVBOOK
            title="Réinitialisation mot de passe",
            categorie='information_generale'
        )
