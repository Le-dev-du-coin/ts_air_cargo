"""
Utilitaires pour la création asynchrone de clients avec Celery
dans l'app agent_chine_app
"""

from .tasks import create_client_account_async
import logging

logger = logging.getLogger(__name__)


def create_client_async(telephone, first_name, last_name, email=None, password=None, send_notifications=True, initiated_by=None):
    """
    Fonction utilitaire pour créer un client de manière asynchrone avec Celery
    
    Args:
        telephone: Numéro de téléphone du client
        first_name: Prénom du client
        last_name: Nom du client  
        email: Email optionnel
        password: Mot de passe optionnel
        send_notifications: Envoyer les notifications WhatsApp
        initiated_by: Agent qui initie la création
        
    Returns:
        AsyncResult: Objet Celery pour suivre la tâche
        
    Example:
        # Créer un client avec notifications automatiques
        task_result = create_client_async(
            telephone="+22376123456",
            first_name="Jean",
            last_name="Dupont",
            email="jean@example.com"
        )
        
        # Suivre le statut de la tâche
        print(f"Task ID: {task_result.id}")
        print(f"Task Status: {task_result.status}")
        
        # Récupérer le résultat (bloquant)
        result = task_result.get()
        if result.get('created'):
            print(f"Client créé: {result['client_name']}")
    """
    try:
        # Créer la tâche de tracking d'abord
        from .models import ClientCreationTask
        from django.contrib.auth import get_user_model
        
        if not initiated_by:
            # Essayer de récupérer l'utilisateur actuel depuis le contexte
            # Si pas disponible, utiliser un agent par défaut
            User = get_user_model()
            try:
                initiated_by = User.objects.filter(is_agent_chine=True).first()
                if not initiated_by:
                    raise Exception("Aucun agent Chine disponible pour initier la tâche")
            except:
                raise Exception("Agent requis pour initier la création de client")
        
        # Créer la tâche de tracking
        client_task = ClientCreationTask.objects.create(
            telephone=telephone,
            first_name=first_name,
            last_name=last_name,
            email=email or '',
            initiated_by=initiated_by,
            status='pending'
        )
        
        logger.info(f"🚀 Tâche création client créée: {client_task.task_id} pour {telephone}")
        
        # Lancer la tâche Celery avec l'ID de la tâche
        task_result = create_client_account_async.delay(client_task.task_id)
        
        # Mettre à jour l'ID Celery
        client_task.celery_task_id = task_result.id
        client_task.save(update_fields=['celery_task_id'])
        
        logger.info(f"📤 Tâche Celery lancée: {task_result.id} pour tâche {client_task.task_id}")
        
        return task_result
        
    except Exception as e:
        logger.error(f"❌ Erreur lancement tâche création client {telephone}: {e}", exc_info=True)
        raise


def create_bulk_clients_async(clients_data, send_notifications=True):
    """
    Créer plusieurs clients de manière asynchrone
    
    Args:
        clients_data: Liste de données clients
        send_notifications: Envoyer les notifications
        
    Returns:
        list: Liste des tâches Celery lancées
        
    Example:
        clients = [
            {
                'telephone': '+22376123456',
                'first_name': 'Jean',
                'last_name': 'Dupont',
                'email': 'jean@example.com'
            },
            {
                'telephone': '+22365789012', 
                'first_name': 'Marie',
                'last_name': 'Martin'
            }
        ]
        
        tasks = create_bulk_clients_async(clients)
        print(f"{len(tasks)} tâches lancées")
    """
    tasks = []
    
    try:
        for client_data in clients_data:
            task = create_client_async(
                telephone=client_data['telephone'],
                first_name=client_data['first_name'],
                last_name=client_data['last_name'],
                email=client_data.get('email'),
                password=client_data.get('password'),
                send_notifications=send_notifications
            )
            tasks.append(task)
            
        logger.info(f"📤 {len(tasks)} tâches création client lancées en masse")
        return tasks
        
    except Exception as e:
        logger.error(f"❌ Erreur création clients en masse: {e}", exc_info=True)
        raise


def get_client_creation_status(task_id):
    """
    Récupérer le statut d'une tâche de création de client
    
    Args:
        task_id: ID de la tâche Celery
        
    Returns:
        dict: Statut et résultat de la tâche
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        status_info = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else False,
            'result': None,
            'error': None
        }
        
        if result.ready():
            try:
                if result.successful():
                    status_info['result'] = result.result
                else:
                    status_info['error'] = str(result.info)
            except Exception as e:
                status_info['error'] = str(e)
        
        return status_info
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération statut tâche {task_id}: {e}")
        return {
            'task_id': task_id,
            'status': 'ERROR',
            'error': str(e)
        }


def wait_for_client_creation(task_result, timeout=30):
    """
    Attendre la fin d'une tâche de création de client
    
    Args:
        task_result: AsyncResult de la tâche
        timeout: Timeout en secondes
        
    Returns:
        dict: Résultat de la création
        
    Raises:
        TimeoutError: Si la tâche n'est pas terminée dans le délai
    """
    try:
        result = task_result.get(timeout=timeout)
        logger.info(f"✅ Tâche terminée: {task_result.id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur attente tâche {task_result.id}: {e}")
        raise


# Fonctions pour intégration dans les vues Django

def create_client_for_view(request, telephone, first_name, last_name, email=None, password=None):
    """
    Créer un client depuis une vue Django avec gestion des erreurs
    
    Args:
        request: Objet request Django
        telephone: Numéro de téléphone
        first_name: Prénom
        last_name: Nom
        email: Email optionnel
        password: Mot de passe optionnel
        
    Returns:
        dict: Résultat avec task_id et infos
    """
    try:
        task_result = create_client_async(
            telephone=telephone,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            send_notifications=True
        )
        
        return {
            'success': True,
            'task_id': task_result.id,
            'message': f'Création du client {first_name} {last_name} en cours...',
            'telephone': telephone
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur création client depuis vue: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'telephone': telephone
        }


def check_client_creation_progress(task_ids):
    """
    Vérifier le progrès de plusieurs créations de clients
    
    Args:
        task_ids: Liste des IDs de tâches
        
    Returns:
        dict: Statistiques de progression
    """
    stats = {
        'total': len(task_ids),
        'completed': 0,
        'failed': 0,
        'pending': 0,
        'details': []
    }
    
    for task_id in task_ids:
        status = get_client_creation_status(task_id)
        stats['details'].append(status)
        
        if status['status'] == 'SUCCESS':
            stats['completed'] += 1
        elif status['status'] == 'FAILURE':
            stats['failed'] += 1
        else:
            stats['pending'] += 1
    
    return stats