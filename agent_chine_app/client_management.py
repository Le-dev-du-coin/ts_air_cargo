"""
Module pour la gestion automatique des comptes clients
depuis l'application agent_chine_app
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from authentication.services import UserCreationService
from notifications_app.services import NotificationService
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class ClientAccountManager:
    """
    Gestionnaire pour la création automatique des comptes clients
    """
    
    @staticmethod
    @transaction.atomic
    def get_or_create_client(telephone, first_name, last_name, email=None, notify=True):
        """
        Récupère ou crée un compte client et envoie les identifiants si nouveau
        
        Args:
            telephone (str): Numéro de téléphone du client
            first_name (str): Prénom du client
            last_name (str): Nom du client
            email (str, optional): Email du client
            notify (bool): Envoyer les identifiants par notification
            
        Returns:
            dict: {
                'client': User instance,
                'created': bool,
                'password': str ou None,
                'notification_sent': bool
            }
        """
        try:
            # Nettoyer le numéro de téléphone
            telephone = ClientAccountManager._clean_phone_number(telephone)
            
            # Utiliser le service de création d'utilisateurs
            result = UserCreationService.create_client_account(
                telephone=telephone,
                first_name=first_name,
                last_name=last_name,
                email=email
            )
            
            notification_sent = False
            
            # Si un nouveau compte a été créé, envoyer les identifiants
            if result['created'] and notify:
                try:
                    notification_sent = NotificationService.send_client_creation_notification(
                        user=result['user'],
                        temp_password=result['password']
                    )
                    logger.info(f"Compte client créé et notification envoyée: {telephone}")
                except Exception as e:
                    logger.error(f"Erreur envoi notification pour {telephone}: {str(e)}")
            
            return {
                'client': result['user'],
                'created': result['created'],
                'password': result['password'],
                'notification_sent': notification_sent
            }
            
        except ValidationError as e:
            logger.error(f"Erreur validation lors création client {telephone}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue création client {telephone}: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def get_or_create_client_with_password(telephone, first_name, last_name, email=None, password=None, notify=True):
        """
        Crée ou récupère un client avec un mot de passe personnalisé (si fourni)
        
        Args:
            telephone (str): Numéro de téléphone du client
            first_name (str): Prénom du client
            last_name (str): Nom du client
            email (str, optional): Email du client
            password (str, optional): Mot de passe personnalisé
            notify (bool): Envoyer les identifiants par notification
            
        Returns:
            dict: {
                'client': User instance,
                'created': bool,
                'password': str (mot de passe utilisé),
                'notification_sent': bool
            }
        """
        try:
            # Nettoyer le numéro de téléphone
            telephone = ClientAccountManager._clean_phone_number(telephone)
            
            # Vérifier si l'utilisateur existe déjà
            try:
                user = User.objects.get(telephone=telephone)
                return {
                    'client': user,
                    'created': False,
                    'password': None,  # Pas de nouveau mot de passe
                    'notification_sent': False
                }
            except User.DoesNotExist:
                # Créer un nouveau compte
                if password and password.strip():
                    # Utiliser le mot de passe fourni
                    final_password = password.strip()
                else:
                    # Générer un mot de passe temporaire
                    final_password = UserCreationService.generate_temp_password()
                
                user = User.objects.create_user(
                    telephone=telephone,
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"{telephone}@temp.ts-cargo.com",
                    password=final_password,
                    role='client',
                    is_client=True
                )
                
                notification_sent = False
                
                # Si un nouveau compte a été créé, envoyer les identifiants
                if notify:
                    try:
                        notification_sent = NotificationService.send_client_creation_notification(
                            user=user,
                            temp_password=final_password
                        )
                        logger.info(f"Compte client créé et notification envoyée: {telephone}")
                    except Exception as e:
                        logger.error(f"Erreur envoi notification pour {telephone}: {str(e)}")
                
                return {
                    'client': user,
                    'created': True,
                    'password': final_password,
                    'notification_sent': notification_sent
                }
                
        except ValidationError as e:
            logger.error(f"Erreur validation lors création client {telephone}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue création client {telephone}: {str(e)}")
            raise
    
    @staticmethod
    def _clean_phone_number(telephone):
        """
        Nettoie et standardise le numéro de téléphone
        Gère les formats: 99281899, 0099281899, 22399281899, +22399281899
        """
        if not telephone:
            raise ValidationError("Le numéro de téléphone est requis")
        
        # Retirer les espaces et caractères spéciaux sauf le +
        phone = ''.join(filter(lambda x: x.isdigit() or x == '+', telephone.strip()))
        
        # Retirer le + initial pour traitement
        if phone.startswith('+'):
            phone = phone[1:]
        
        # Retirer les zéros initiaux
        phone = phone.lstrip('0')
        
        # Logique de standardisation
        if phone.startswith('223'):
            # Numéro avec indicatif Mali complet: 22399281899 -> +22399281899
            return f"+{phone}"
        elif phone.startswith('76') or phone.startswith('65') or phone.startswith('90') or phone.startswith('99'):
            # Numéro sans indicatif: 99281899 -> +22399281899
            return f"+223{phone}"
        elif len(phone) >= 8 and phone.isdigit():
            # Autres numéros longs, ajouter l'indicatif Mali par défaut
            return f"+223{phone}"
        else:
            # Format non reconnu, ajouter l'indicatif Mali
            return f"+223{phone}"
    
    @staticmethod
    def resend_client_credentials(telephone):
        """
        Renvoie les identifiants à un client existant avec un nouveau mot de passe
        """
        try:
            user = User.objects.get(telephone=telephone, role='client')
            
            # Générer un nouveau mot de passe temporaire
            temp_password = UserCreationService.generate_temp_password()
            user.set_password(temp_password)
            user.save()
            
            # Envoyer la notification
            notification_sent = NotificationService.send_client_creation_notification(
                user=user,
                temp_password=temp_password
            )
            
            logger.info(f"Nouveaux identifiants envoyés à {telephone}")
            
            return {
                'success': True,
                'password': temp_password,
                'notification_sent': notification_sent
            }
            
        except User.DoesNotExist:
            logger.error(f"Client non trouvé: {telephone}")
            return {'success': False, 'error': 'Client non trouvé'}
        except Exception as e:
            logger.error(f"Erreur renvoi identifiants {telephone}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def bulk_create_clients(clients_data):
        """
        Création en masse de comptes clients
        
        Args:
            clients_data (list): Liste de dict contenant les infos clients
                [{'telephone': '+22376123456', 'first_name': 'Jean', 'last_name': 'Doe'}, ...]
                
        Returns:
            dict: Statistiques de création
        """
        results = {
            'created': 0,
            'existing': 0,
            'errors': []
        }
        
        for client_data in clients_data:
            try:
                result = ClientAccountManager.get_or_create_client(
                    telephone=client_data['telephone'],
                    first_name=client_data['first_name'],
                    last_name=client_data['last_name'],
                    email=client_data.get('email'),
                    notify=client_data.get('notify', True)
                )
                
                if result['created']:
                    results['created'] += 1
                else:
                    results['existing'] += 1
                    
            except Exception as e:
                results['errors'].append({
                    'client': client_data,
                    'error': str(e)
                })
        
        logger.info(f"Création en masse terminée: {results['created']} créés, {results['existing']} existants, {len(results['errors'])} erreurs")
        return results

# Fonctions utilitaires pour les vues Django

def create_client_for_colis(client_info):
    """
    Fonction simplifiée pour créer un client lors de la création d'un colis
    
    Args:
        client_info (dict): Informations du client
        
    Returns:
        User: Instance du client créé ou existant
    """
    result = ClientAccountManager.get_or_create_client(
        telephone=client_info['telephone'],
        first_name=client_info['first_name'],
        last_name=client_info['last_name'],
        email=client_info.get('email'),
        notify=True
    )
    
    return result['client']

def send_client_credentials(telephone):
    """
    Fonction pour renvoyer les identifiants depuis une vue
    """
    return ClientAccountManager.resend_client_credentials(telephone)
