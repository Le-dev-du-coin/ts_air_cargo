"""
Tâches Celery pour l'app agent_chine
Gestion asynchrone de la création et modification de colis
"""

import os
import logging
import uuid
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.conf import settings
from PIL import Image
import tempfile

from .models import ColisCreationTask, Colis, Client, Lot
from .client_management import ClientAccountManager
from notifications_app.tasks import notify_colis_created, notify_colis_updated
from whatsapp_monitoring_app.tasks import send_whatsapp_async

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, 
    autoretry_for=(Exception,), 
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    priority=5,  # Priorité moyenne pour la création
    time_limit=300,  # 5 minutes max
    soft_time_limit=240  # Warning à 4 minutes
)
def create_colis_async(self, task_id):
    """
    Tâche principale de création asynchrone de colis
    
    Args:
        task_id (str): Identifiant unique de la tâche ColisCreationTask
        
    Returns:
        dict: Résultat de l'opération avec statut et détails
    """
    task = None
    
    try:
        # Récupérer la tâche
        task = ColisCreationTask.objects.get(task_id=task_id)
        task.celery_task_id = self.request.id
        task.mark_as_started()
        
        logger.info(f"🚀 Début création asynchrone colis - Tâche {task_id}")
        
        # Étape 1: Validation des données
        task.update_progress("Validation des données du colis", 20)
        
        colis_data = task.colis_data
        client = Client.objects.get(id=colis_data['client_id'])
        lot = task.lot
        
        # Validation business
        if lot.statut != 'ouvert':
            raise ValueError(f"Impossible d'ajouter un colis au lot {lot.numero_lot} (statut: {lot.statut})")
        
        # Étape 2: Traitement de l'image (optimisé avec paramètres)
        processed_image = None
        skip_image_processing = getattr(settings, 'SKIP_IMAGE_PROCESSING_IN_DEV', False)
        
        if task.original_image_path and os.path.exists(task.original_image_path) and not skip_image_processing:
            task.update_progress("Traitement de l'image du colis", 40)
            task.status = 'image_uploading'
            task.save(update_fields=['status'])
            
            try:
                processed_image = process_colis_image(task.original_image_path, task_id)
                logger.info(f"📸 Image traitée pour tâche {task_id}")
            except Exception as img_error:
                logger.warning(f"⚠️ Erreur traitement image pour tâche {task_id}: {img_error}")
                # Continuer sans image plutôt que d'échouer
                processed_image = None
        elif skip_image_processing:
            logger.debug(f"⏩ Traitement image ignoré (mode développement) pour tâche {task_id}")
        else:
            logger.debug(f"🖼️ Pas d'image à traiter pour tâche {task_id}")
        
        # Étape 3: Création du colis en base (optimisé)
        task.update_progress("Création du colis en base de données", 60)
        task.current_step = "Préparation des données"
        task.save(update_fields=['progress_percentage', 'current_step'])
        
        # Préparation des données du colis
        colis_params = {
            'client': client,
            'lot': lot,
            'type_transport': colis_data['type_transport'],
            'longueur': float(colis_data.get('longueur', 0)),
            'largeur': float(colis_data.get('largeur', 0)),
            'hauteur': float(colis_data.get('hauteur', 0)),
            'poids': float(colis_data.get('poids', 0)),
            'mode_paiement': colis_data.get('mode_paiement', 'non_paye'),
            'statut': colis_data.get('statut', 'receptionne_chine'),
            'description': colis_data.get('description', ''),
        }
        
        # Ajouter le prix manuel si fourni (déjà calculé dans la vue)
        if colis_data.get('prix_transport_manuel'):
            colis_params['prix_transport_manuel'] = float(colis_data['prix_transport_manuel'])
        
        # Ajouter l'image si traitée
        if processed_image:
            colis_params['image'] = processed_image
        
        # Création du colis (le prix sera calculé automatiquement dans save())
        colis = Colis.objects.create(**colis_params)
        
        logger.info(f"📦 Colis {colis.numero_suivi} créé avec succès")
        
        # Étape 4: Calcul du prix (déjà fait automatiquement dans Colis.save())
        task.update_progress("Calcul du prix automatique", 80)
        task.status = 'price_calculating'
        task.save(update_fields=['status'])
        
        # Recharger pour avoir le prix calculé
        colis.refresh_from_db()
        
        # Étape 5: Envoi des notifications
        task.update_progress("Envoi des notifications", 90)
        task.status = 'notification_sending'
        task.save(update_fields=['status'])
        
        # Lancer la tâche de notification (asynchrone aussi)
        try:
            notify_colis_created.delay(colis.id, initiated_by_id=task.initiated_by.id)
        except Exception as notif_error:
            logger.warning(f"⚠️ Erreur notification pour colis {colis.numero_suivi}: {notif_error}")
            # Ne pas faire échouer la création pour un problème de notification
        
        # Finalisation
        task.mark_as_completed(colis)
        
        # Nettoyage des fichiers temporaires
        cleanup_temp_files(task.original_image_path)
        
        logger.info(f"✅ Colis {colis.numero_suivi} créé avec succès via tâche asynchrone {task_id}")
        
        return {
            'success': True,
            'colis_id': colis.id,
            'numero_suivi': colis.numero_suivi,
            'prix_calcule': float(colis.prix_calcule),
            'task_id': task_id,
            'duration': task.get_duration().total_seconds() if task.get_duration() else None
        }
        
    except Exception as e:
        error_msg = f"Erreur création colis: {str(e)}"
        logger.error(f"❌ Tâche {task_id}: {error_msg}", exc_info=True)
        
        # Marquer la tâche comme échouée
        if task:
            task.mark_as_failed(error_msg)
            # Nettoyage en cas d'échec
            cleanup_temp_files(task.original_image_path)
        
        # Retry si possible
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry {self.request.retries + 1}/{self.max_retries} pour tâche {task_id}")
            raise self.retry(countdown=300 * (2 ** self.request.retries))  # Backoff exponentiel
        
        return {
            'success': False,
            'error': error_msg,
            'task_id': task_id,
            'retry_count': self.request.retries
        }


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def update_colis_async(self, task_id):
    """
    Tâche principale de modification asynchrone de colis
    
    Args:
        task_id (str): Identifiant unique de la tâche ColisCreationTask
        
    Returns:
        dict: Résultat de l'opération avec statut et détails
    """
    task = None
    
    try:
        # Récupérer la tâche
        task = ColisCreationTask.objects.get(task_id=task_id)
        task.celery_task_id = self.request.id
        task.mark_as_started()
        
        logger.info(f"🔄 Début modification asynchrone colis - Tâche {task_id}")
        
        # Étape 1: Validation des données
        task.update_progress("Validation des données modifiées", 20)
        
        colis_data = task.colis_data
        colis = task.colis  # Le colis existe déjà pour une modification
        
        if not colis:
            raise ValueError("Aucun colis associé à cette tâche de modification")
        
        # Vérifier que le colis peut être modifié
        if colis.statut in ['livre', 'perdu']:
            raise ValueError(f"Impossible de modifier le colis {colis.numero_suivi} (statut: {colis.statut})")
        
        # Étape 2: Traitement de l'image (si nouvelle image)
        task.update_progress("Traitement de la nouvelle image", 40)
        task.status = 'image_uploading'
        task.save(update_fields=['status'])
        
        if task.original_image_path and os.path.exists(task.original_image_path):
            processed_image = process_colis_image(task.original_image_path, task_id)
            colis.image = processed_image
            logger.info(f"📸 Nouvelle image traitée pour colis {colis.numero_suivi}")
        
        # Étape 3: Mise à jour du colis
        task.update_progress("Mise à jour des données du colis", 60)
        
        # Mise à jour des champs
        if 'client_id' in colis_data:
            client = Client.objects.get(id=colis_data['client_id'])
            colis.client = client
        
        # Mise à jour des propriétés
        colis.type_transport = colis_data.get('type_transport', colis.type_transport)
        colis.longueur = float(colis_data.get('longueur', colis.longueur))
        colis.largeur = float(colis_data.get('largeur', colis.largeur))
        colis.hauteur = float(colis_data.get('hauteur', colis.hauteur))
        colis.poids = float(colis_data.get('poids', colis.poids))
        
        # Mettre à jour le prix manuel si fourni (déjà calculé dans la vue)
        if 'prix_transport_manuel' in colis_data:
            colis.prix_transport_manuel = colis_data['prix_transport_manuel']
            
        colis.mode_paiement = colis_data.get('mode_paiement', colis.mode_paiement)
        colis.statut = colis_data.get('statut', colis.statut)
        colis.description = colis_data.get('description', colis.description)
        
        # Recalculer le prix si les dimensions/poids ont changé
        old_price = colis.prix_calcule
        colis.prix_calcule = colis.calculer_prix_automatique()
        
        # Sauvegarder les modifications
        colis.save()
        
        logger.info(f"📦 Colis {colis.numero_suivi} modifié avec succès")
        
        # Étape 4: Envoi des notifications
        task.update_progress("Envoi des notifications de modification", 90)
        task.status = 'notification_sending'
        task.save(update_fields=['status'])
        
        try:
            notify_colis_updated.delay(colis.id, initiated_by_id=task.initiated_by.id)
        except Exception as notif_error:
            logger.warning(f"⚠️ Erreur notification modification pour colis {colis.numero_suivi}: {notif_error}")
        
        # Finalisation
        task.mark_as_completed(colis)
        
        # Nettoyage des fichiers temporaires
        cleanup_temp_files(task.original_image_path)
        
        logger.info(f"✅ Colis {colis.numero_suivi} modifié avec succès via tâche asynchrone {task_id}")
        
        return {
            'success': True,
            'colis_id': colis.id,
            'numero_suivi': colis.numero_suivi,
            'prix_calcule': float(colis.prix_calcule),
            'price_changed': float(old_price) != float(colis.prix_calcule),
            'task_id': task_id,
            'duration': task.get_duration().total_seconds() if task.get_duration() else None
        }
        
    except Exception as e:
        error_msg = f"Erreur modification colis: {str(e)}"
        logger.error(f"❌ Tâche {task_id}: {error_msg}", exc_info=True)
        
        if task:
            task.mark_as_failed(error_msg)
            cleanup_temp_files(task.original_image_path)
        
        # Retry si possible
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry {self.request.retries + 1}/{self.max_retries} pour modification tâche {task_id}")
            raise self.retry(countdown=300 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': error_msg,
            'task_id': task_id,
            'retry_count': self.request.retries
        }


def process_colis_image(temp_image_path, task_id):
    """
    Traite une image de colis : compression, redimensionnement, validation
    Optimisé pour les performances et la gestion d'erreurs
    
    Args:
        temp_image_path (str): Chemin vers l'image temporaire
        task_id (str): ID de la tâche pour le nommage
        
    Returns:
        ContentFile: Fichier traité prêt pour Django
    """
    start_time = timezone.now()
    temp_output_path = None
    
    try:
        # Vérification préliminaire du fichier
        file_size = os.path.getsize(temp_image_path)
        if file_size > 50 * 1024 * 1024:  # 50MB max
            raise ValueError(f"Image trop volumineuse: {file_size / 1024 / 1024:.1f}MB (max 50MB)")
        
        logger.info(f"📸 Début traitement image {file_size / 1024:.0f}KB pour tâche {task_id}")
        
        # Ouvrir et traiter l'image avec optimisations
        with Image.open(temp_image_path) as img:
            # Validation du format
            if img.format not in ['JPEG', 'PNG', 'BMP', 'TIFF', 'WEBP']:
                raise ValueError(f"Format d'image non supporté: {img.format}")
            
            original_size = img.size
            
            # Convertir en RGB si nécessaire (optimisé)
            if img.mode in ('RGBA', 'P', 'LA'):
                # Pour RGBA, créer un fond blanc pour préserver la qualité
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])  # Use alpha as mask
                    img = background
                else:
                    img = img.convert('RGB')
                logger.debug(f"📐 Conversion couleur pour tâche {task_id}")
            
            # Redimensionnement optimisé avec plusieurs seuils
            max_size = 1600
            if max(img.size) > max_size:
                # Utiliser un algorithme plus rapide pour les très grandes images
                if max(img.size) > 3000:
                    # Première réduction rapide
                    img.thumbnail((2000, 2000), Image.Resampling.NEAREST)
                
                # Réduction finale avec qualité
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"📐 Image redimensionnée {original_size} -> {img.size} pour tâche {task_id}")
            
            # Sauvegarder avec optimisations de compression
            temp_output_path = tempfile.mktemp(suffix='.jpg')
            
            # Adapter la qualité selon la taille finale
            quality = 90 if max(img.size) < 800 else 85
            
            img.save(
                temp_output_path,
                format='JPEG',
                quality=quality,
                optimize=True,
                progressive=True  # Pour un chargement progressif
            )
            
            # Lire le fichier traité
            with open(temp_output_path, 'rb') as processed_file:
                content = processed_file.read()
            
            # Générer un nom de fichier unique
            filename = f"colis_{task_id}_{uuid.uuid4().hex[:8]}.jpg"
            
            # Log des performances
            processing_time = (timezone.now() - start_time).total_seconds()
            final_size = len(content)
            compression_ratio = (file_size - final_size) / file_size * 100
            
            logger.info(
                f"✅ Image traitée pour tâche {task_id}: "
                f"{file_size/1024:.0f}KB -> {final_size/1024:.0f}KB "
                f"({compression_ratio:.0f}% compression) en {processing_time:.1f}s"
            )
            
            return ContentFile(content, name=filename)
            
    except Exception as e:
        error_msg = f"Erreur traitement image pour tâche {task_id}: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        raise ValueError(f"Impossible de traiter l'image: {str(e)}")
    
    finally:
        # Nettoyage du fichier temporaire de sortie
        if temp_output_path and os.path.exists(temp_output_path):
            try:
                os.unlink(temp_output_path)
                logger.debug(f"🧹 Fichier temporaire traité supprimé: {temp_output_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Erreur nettoyage fichier temporaire {temp_output_path}: {cleanup_error}")


def cleanup_temp_files(temp_path):
    """
    Nettoie les fichiers temporaires
    
    Args:
        temp_path (str): Chemin vers le fichier temporaire à supprimer
    """
    if temp_path and os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
            logger.debug(f"🧹 Fichier temporaire supprimé: {temp_path}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur suppression fichier temporaire {temp_path}: {e}")


@shared_task
def retry_failed_tasks():
    """
    Tâche périodique pour relancer les tâches échouées éligibles au retry
    À programmer avec celery beat
    """
    from django.utils import timezone
    
    try:
        # Rechercher les tâches échouées prêtes pour un retry
        now = timezone.now()
        retry_tasks = ColisCreationTask.objects.filter(
            status='failed_retry',
            next_retry_at__lte=now,
            retry_count__lt=3  # Max retries par défaut
        )
        
        retry_count = 0
        for task in retry_tasks[:20]:  # Limiter à 20 par batch
            try:
                logger.info(f"🔄 Relance automatique de la tâche {task.task_id}")
                
                # Relancer la tâche appropriée
                if task.operation_type == 'create':
                    create_colis_async.delay(task.task_id)
                else:
                    update_colis_async.delay(task.task_id)
                
                retry_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erreur relance tâche {task.task_id}: {e}")
                task.mark_as_failed(f"Erreur relance automatique: {str(e)}")
        
        logger.info(f"🔄 {retry_count} tâches relancées automatiquement")
        
        return {
            'success': True,
            'retried_count': retry_count
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la relance automatique des tâches: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_tasks():
    """
    Tâche de nettoyage des anciennes tâches terminées
    À programmer hebdomadairement
    """
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Supprimer les tâches terminées > 30 jours
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_completed_tasks = ColisCreationTask.objects.filter(
            status='completed',
            completed_at__lt=cutoff_date
        )
        completed_deleted = old_completed_tasks.count()
        old_completed_tasks.delete()
        
        # Supprimer les tâches échouées définitivement > 7 jours
        failed_cutoff = timezone.now() - timedelta(days=7)
        old_failed_tasks = ColisCreationTask.objects.filter(
            status='failed_final',
            created_at__lt=failed_cutoff
        )
        failed_deleted = old_failed_tasks.count()
        old_failed_tasks.delete()
        
        # Supprimer les tâches annulées > 3 jours
        cancelled_cutoff = timezone.now() - timedelta(days=3)
        old_cancelled_tasks = ColisCreationTask.objects.filter(
            status='cancelled',
            created_at__lt=cancelled_cutoff
        )
        cancelled_deleted = old_cancelled_tasks.count()
        old_cancelled_tasks.delete()
        
        total_deleted = completed_deleted + failed_deleted + cancelled_deleted
        
        logger.info(f"🧹 Nettoyage: {total_deleted} tâches supprimées "
                   f"({completed_deleted} complétées, {failed_deleted} échouées, {cancelled_deleted} annulées)")
        
        return {
            'success': True,
            'total_deleted': total_deleted,
            'completed_deleted': completed_deleted,
            'failed_deleted': failed_deleted,
            'cancelled_deleted': cancelled_deleted
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du nettoyage des tâches: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def create_client_account_async(self, telephone, first_name, last_name, email=None, password=None, send_notifications=True):
    """
    Tâche asynchrone pour créer un compte client avec notifications WhatsApp via monitoring
    
    Args:
        telephone: Numéro de téléphone du client
        first_name: Prénom du client  
        last_name: Nom du client
        email: Email optionnel
        password: Mot de passe optionnel
        send_notifications: Envoyer les notifications WhatsApp
        
    Returns:
        dict: Résultat de la création avec détails
    """
    try:
        logger.info(f"🚀 Début création client asynchrone: {telephone}")
        
        # Créer ou récupérer le client (synchrone)
        if password:
            client_result = ClientAccountManager.get_or_create_client_with_password(
                telephone=telephone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                notify=False  # On va gérer les notifications async séparément
            )
        else:
            client_result = ClientAccountManager.get_or_create_client(
                telephone=telephone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                notify=False  # On va gérer les notifications async séparément
            )
        
        result = {
            'client_id': client_result['client'].id,
            'client_phone': client_result['client'].telephone,
            'client_name': client_result['client'].get_full_name(),
            'created': client_result['created'],
            'password': client_result['password'] if client_result['created'] else None,
            'celery_task_id': self.request.id,
            'notifications_sent': []
        }
        
        # Envoyer les notifications de manière asynchrone si demandé et nouveau client
        if send_notifications and client_result['created']:
            
            # Message avec identifiants
            if client_result['password']:
                credentials_message = f"""
🎉 Bienvenue chez TS Air Cargo !

👤 Nom: {client_result['client'].get_full_name()}
📞 Téléphone: {client_result['client'].telephone}
✉️ Email: {client_result['client'].email}

🔑 Mot de passe: {client_result['password']}
⚠️ Veuillez changer ce mot de passe lors de votre première connexion.

🌐 Connectez-vous sur notre plateforme pour gérer vos envois.

Équipe TS Air Cargo 🚀
"""
                
                # Envoyer notification avec identifiants (asynchrone)
                credentials_task = send_whatsapp_async(
                    user=client_result['client'],
                    message_content=credentials_message,
                    source_app='agent_chine',
                    message_type='credentials',
                    category='client_creation',
                    title="Identifiants client TS Air Cargo",
                    priority=1,  # Haute priorité
                    max_attempts=5,
                    sender_role='agent_chine',
                    region_override='chine',
                    context_data={
                        'client_id': client_result['client'].id,
                        'action': 'creation_client_async',
                        'has_credentials': True,
                        'parent_task_id': self.request.id
                    }
                )
                
                result['notifications_sent'].append({
                    'type': 'credentials',
                    'task_id': credentials_task.id,
                    'status': 'scheduled'
                })
                
                logger.info(f"📤 Notification identifiants programmée pour {telephone} (task: {credentials_task.id})")
            
            # Message de bienvenue supprimé - seul le message avec identifiants est envoyé
            logger.info(f"ℹ️ Message de bienvenue supprimé pour éviter la duplication pour {telephone}")
        
        if client_result['created']:
            logger.info(f"✅ Client {telephone} créé avec succès et notifications programmées")
        else:
            logger.info(f"ℹ️ Client {telephone} existait déjà")
        
        return result
        
    except Exception as e:
        error_msg = f"Erreur création client async {telephone}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Retry automatique
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry création client async {telephone} (tentative {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': error_msg,
            'telephone': telephone,
            'celery_task_id': self.request.id,
            'retries_exhausted': True
        }
