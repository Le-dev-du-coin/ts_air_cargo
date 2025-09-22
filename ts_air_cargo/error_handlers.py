"""
Gestionnaires d'erreurs personnalisés pour TS Air Cargo
"""

from django.shortcuts import render
from django.http import HttpResponseServerError, HttpResponseNotFound
from django.template import RequestContext
import logging
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)

def handler500(request, *args, **kwargs):
    """
    Gestionnaire d'erreur 500 personnalisé avec logging
    """
    # Générer un ID d'erreur unique pour le suivi
    error_id = str(uuid.uuid4())[:8].upper()
    
    # Logger l'erreur avec plus de détails
    logger.error(
        f"ERROR_500 [{error_id}] - {request.method} {request.path} - "
        f"User: {getattr(request.user, 'id', 'Anonymous')} - "
        f"IP: {request.META.get('REMOTE_ADDR', 'Unknown')} - "
        f"UserAgent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}"
    )
    
    context = {
        'error_id': error_id,
        'timestamp': timezone.now(),
        'path': request.path,
        'method': request.method
    }
    
    try:
        return render(request, '500.html', context, status=500)
    except Exception:
        # Fallback si le template n'existe pas
        return HttpResponseServerError(
            f'<h1>Erreur Interne du Serveur</h1>'
            f'<p>Code d\'erreur: {error_id}</p>'
            f'<p>Notre équipe technique a été notifiée.</p>'
            f'<a href="/">Retour à l\'accueil</a>'
        )

def handler404(request, exception=None):
    """
    Gestionnaire d'erreur 404 personnalisé
    """
    # Logger les 404 pour détecter les patterns d'attaque
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if any(bot in user_agent.lower() for bot in ['bot', 'crawler', 'spider']):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    logger.log(
        log_level,
        f"404 - {request.method} {request.path} - "
        f"Referer: {request.META.get('HTTP_REFERER', 'None')} - "
        f"IP: {request.META.get('REMOTE_ADDR', 'Unknown')}"
    )
    
    context = {
        'request_path': request.path,
        'referer': request.META.get('HTTP_REFERER', ''),
        'timestamp': timezone.now()
    }
    
    try:
        return render(request, '404.html', context, status=404)
    except Exception:
        # Fallback si le template n'existe pas
        return HttpResponseNotFound(
            f'<h1>Page non trouvée</h1>'
            f'<p>La page "{request.path}" n\'existe pas.</p>'
            f'<a href="/">Retour à l\'accueil</a>'
        )

def handler403(request, exception=None):
    """
    Gestionnaire d'erreur 403 personnalisé
    """
    logger.warning(
        f"403 Forbidden - {request.method} {request.path} - "
        f"User: {getattr(request.user, 'id', 'Anonymous')} - "
        f"IP: {request.META.get('REMOTE_ADDR', 'Unknown')}"
    )
    
    context = {
        'request_path': request.path,
        'user': request.user if request.user.is_authenticated else None
    }
    
    return render(request, '403.html', context, status=403)
