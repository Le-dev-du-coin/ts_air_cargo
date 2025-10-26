"""
Vue dédiée pour la réinitialisation de mot de passe par SMS uniquement
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Client
from .views import agent_chine_required
from authentication.services import UserCreationService
from notifications_app.orange_sms_service import orange_sms_service
from notifications_app.models import SMSLog
import logging

logger = logging.getLogger(__name__)


@agent_chine_required
@require_POST
def client_reset_password_sms_view(request, client_id):
    """
    Réinitialise le mot de passe d'un client et envoie UNIQUEMENT par SMS
    Utile pour forcer l'envoi SMS si WhatsApp ne fonctionne pas
    """
    client = get_object_or_404(Client, id=client_id)
    user = client.user
    
    # Vérifier que le service SMS est configuré
    if not orange_sms_service.is_configured():
        messages.error(
            request,
            "❌ Service SMS Orange non configuré. Veuillez configurer ORANGE_SMS_CLIENT_ID et ORANGE_SMS_CLIENT_SECRET dans .env"
        )
        return redirect('agent_chine:client_detail', client_id=client_id)
    
    try:
        # Générer un nouveau mot de passe
        new_password = UserCreationService.generate_temp_password()
        
        # Mettre à jour le mot de passe
        user.set_password(new_password)
        user.has_changed_default_password = False
        user.save()
        
        logger.info(f"Réinitialisation mot de passe SMS pour {user.telephone}")
        
        # Préparer le message SMS (court pour économiser les caractères)
        sms_message = (
            f"🔑 Réinitialisation mot de passe\n"
            f"Identifiant: {user.telephone}\n"
            f"Mot de passe: {new_password}\n"
            f"Changez-le dès votre première connexion.\n"
            f"TS Air Cargo"
        )
        
        # Créer le log SMS
        sms_log = SMSLog.objects.create(
            user=user,
            destinataire_telephone=user.telephone,
            message=sms_message,
            provider='orange',
            statut='pending',
            metadata={
                'type': 'password_reset_sms_only',
                'initiated_by': request.user.telephone
            }
        )
        
        # Envoyer le SMS
        logger.info(f"Envoi SMS Orange vers {user.telephone}")
        success, message_id, response_data = orange_sms_service.send_sms(
            user.telephone, 
            sms_message
        )
        
        if success:
            # Mettre à jour le log
            sms_log.mark_as_sent(message_id)
            
            messages.success(
                request,
                f"✅ Mot de passe réinitialisé avec succès ! "
                f"SMS envoyé à {user.telephone} (ID: {message_id})"
            )
            logger.info(f"SMS Orange envoyé avec succès - ID: {message_id}")
        else:
            # Marquer comme échoué
            sms_log.mark_as_failed(message_id)
            
            messages.warning(
                request,
                f"⚠️ Mot de passe réinitialisé mais l'envoi SMS a échoué. "
                f"Erreur: {message_id}\n"
                f"Nouveau mot de passe : {new_password}"
            )
            logger.error(f"Échec envoi SMS Orange: {message_id}")
            
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation SMS: {str(e)}")
        messages.error(
            request,
            f"❌ Erreur lors de la réinitialisation : {str(e)}"
        )
    
    return redirect('agent_chine:client_detail', client_id=client_id)
