"""
Vue dédiée pour l'envoi de SMS personnalisés aux clients
"""

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from .models import Client
from .views import agent_chine_required
from notifications_app.orange_sms_service import orange_sms_service
from notifications_app.models import SMSLog
import logging

logger = logging.getLogger(__name__)


@agent_chine_required
@require_http_methods(["GET", "POST"])
def send_custom_sms_view(request, client_id):
    """
    Permet à l'agent d'envoyer un SMS personnalisé au client
    GET: Affiche le formulaire
    POST: Envoie le SMS
    """
    client = get_object_or_404(Client, id=client_id)
    user = client.user
    
    # Vérifier que le service SMS est configuré
    if not orange_sms_service.is_configured():
        messages.error(
            request,
            "❌ Service SMS Orange non configuré. Veuillez configurer les identifiants Orange SMS."
        )
        return redirect('agent_chine:client_detail', client_id=client_id)
    
    if request.method == 'GET':
        # Afficher le formulaire
        context = {
            'client': client,
            'user': user,
            'max_length': 160,  # Limite SMS standard
        }
        return render(request, 'agent_chine_app/send_sms_form.html', context)
    
    # POST: Envoyer le SMS
    try:
        message_text = request.POST.get('message', '').strip()
        
        if not message_text:
            messages.error(request, "❌ Le message ne peut pas être vide")
            return redirect('agent_chine:send_custom_sms', client_id=client_id)
        
        if len(message_text) > 160:
            messages.warning(
                request,
                f"⚠️ Message tronqué à 160 caractères (longueur: {len(message_text)})"
            )
            message_text = message_text[:160]
        
        # Ajouter signature
        sms_message = f"{message_text}\n\n- TS Air Cargo"
        
        logger.info(f"Envoi SMS personnalisé à {user.telephone} par {request.user.telephone}")
        
        # Créer le log SMS
        sms_log = SMSLog.objects.create(
            user=user,
            destinataire_telephone=user.telephone,
            message=sms_message,
            provider='orange',
            statut='pending',
            metadata={
                'type': 'custom_message',
                'sent_by': request.user.telephone,
                'sent_by_name': request.user.get_full_name()
            }
        )
        
        # Envoyer le SMS
        success, message_id, response_data = orange_sms_service.send_sms(
            user.telephone, 
            sms_message
        )
        
        if success:
            # Mettre à jour le log
            sms_log.mark_as_sent(message_id)
            
            messages.success(
                request,
                f"✅ SMS envoyé avec succès à {user.get_full_name()} ({user.telephone})"
            )
            logger.info(f"SMS personnalisé envoyé - ID: {message_id}")
        else:
            # Marquer comme échoué
            sms_log.mark_as_failed(message_id)
            
            messages.error(
                request,
                f"❌ Échec de l'envoi SMS. Erreur: {message_id}"
            )
            logger.error(f"Échec envoi SMS personnalisé: {message_id}")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi SMS personnalisé: {str(e)}")
        messages.error(
            request,
            f"❌ Erreur lors de l'envoi : {str(e)}"
        )
    
    return redirect('agent_chine:client_detail', client_id=client_id)


@agent_chine_required
def send_sms_ajax(request, client_id):
    """
    Version AJAX pour envoyer un SMS (pour utilisation avec modal)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    client = get_object_or_404(Client, id=client_id)
    user = client.user
    
    # Vérifier configuration
    if not orange_sms_service.is_configured():
        return JsonResponse({
            'success': False, 
            'error': 'Service SMS non configuré'
        }, status=500)
    
    try:
        message_text = request.POST.get('message', '').strip()
        
        if not message_text:
            return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
        
        if len(message_text) > 160:
            message_text = message_text[:160]
        
        # Ajouter signature
        sms_message = f"{message_text}\n\n- TS Air Cargo"
        
        # Créer le log SMS
        sms_log = SMSLog.objects.create(
            user=user,
            destinataire_telephone=user.telephone,
            message=sms_message,
            provider='orange',
            statut='pending',
            metadata={
                'type': 'custom_message',
                'sent_by': request.user.telephone
            }
        )
        
        # Envoyer
        success, message_id, response_data = orange_sms_service.send_sms(
            user.telephone, 
            sms_message
        )
        
        if success:
            sms_log.mark_as_sent(message_id)
            return JsonResponse({
                'success': True,
                'message': f'SMS envoyé à {user.get_full_name()}',
                'message_id': message_id
            })
        else:
            sms_log.mark_as_failed(message_id)
            return JsonResponse({
                'success': False,
                'error': message_id
            }, status=500)
            
    except Exception as e:
        logger.error(f"Erreur AJAX SMS: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
