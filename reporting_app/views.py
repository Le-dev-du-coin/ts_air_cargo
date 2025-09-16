from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def index(request):
    """
    Vue d'index pour l'application de reporting
    """
    return render(request, 'reporting_app/index.html', {
        'title': 'Reporting'
    })

@login_required
def api_status(request):
    """
    API pour vérifier le statut de l'application reporting
    """
    return JsonResponse({
        'status': 'ok',
        'app': 'reporting_app',
        'message': 'Application de reporting fonctionnelle'
    })
