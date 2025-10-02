# Guide d'Intégration du Système de Monitoring WhatsApp Centralisé avec Celery

## 📋 Vue d'ensemble

Ce système centralise le monitoring des notifications WhatsApp avec les fonctionnalités suivantes :

- **Monitoring centralisé** dans `whatsapp_monitoring_app`
- **Notifications asynchrones** via Celery
- **Créations de clients asynchrones** avec notifications automatiques
- **Monitoring spécifique par app** (chaque app voit seulement ses notifications)
- **Interface admin complète** (voit toutes les notifications)

## 🏗️ Architecture

```
whatsapp_monitoring_app/          # App centralisée
├── models.py                     # Modèles de monitoring
├── services.py                   # Services centralisés
├── tasks.py                      # Tâches Celery pour notifications
└── views.py                      # Vues admin (monitoring complet)

agent_chine_app/
├── tasks.py                      # Tâche création client async
├── client_management.py         # Création client synchrone (sans notif)
├── client_async_utils.py         # Utilitaires Celery
├── whatsapp_views.py            # Monitoring spécifique agent_chine
└── urls.py                       # URLs monitoring

agent_mali_app/
└── whatsapp_integration.py      # Intégration monitoring agent_mali

admin_chine_app/                  # Monitoring complet (admin)
admin_mali_app/                   # Monitoring complet (admin)
```

## 🚀 Fonctionnalités principales

### 1. Notifications WhatsApp Asynchrones

#### Dans agent_chine_app :
```python
from whatsapp_monitoring_app.tasks import send_whatsapp_async

# Envoyer une notification asynchrone
task = send_whatsapp_async(
    user=user,
    message_content="Votre colis est expédié!",
    source_app='agent_chine',
    message_type='expedition',
    category='colis_status',
    title='Expédition colis',
    priority=2
)
```

#### Dans agent_mali_app :
```python
from agent_mali_app.whatsapp_integration import send_whatsapp_notification_mali

# Fonction intégrée spécifique à agent_mali
task = send_whatsapp_notification_mali(
    user=client_user,
    message_content="Votre colis est arrivé au Mali!",
    message_type='delivery',
    category='colis_arrival',
    title='Arrivée colis',
    priority=2
)
```

### 2. Création de Clients Asynchrone

#### Utilisation simple :
```python
from agent_chine_app.client_async_utils import create_client_async

# Créer un client avec notifications automatiques
task_result = create_client_async(
    telephone="+22376123456",
    first_name="Jean",
    last_name="Dupont",
    email="jean@example.com"
)

print(f"Task ID: {task_result.id}")
```

#### Dans les vues Django :
```python
from agent_chine_app.client_async_utils import create_client_for_view

def create_client_view(request):
    if request.method == 'POST':
        result = create_client_for_view(
            request=request,
            telephone=request.POST['telephone'],
            first_name=request.POST['first_name'],
            last_name=request.POST['last_name'],
            email=request.POST.get('email')
        )
        
        if result['success']:
            messages.success(request, f"Client en cours de création (Task: {result['task_id']})")
        else:
            messages.error(request, result['error'])
```

### 3. Monitoring par App

#### Agent Chine - URLs à ajouter :
```python
# agent_chine_app/urls.py
urlpatterns += [
    path('whatsapp/monitoring/', whatsapp_views.whatsapp_monitoring_dashboard, name='whatsapp_monitoring'),
    path('whatsapp/monitoring/list/', whatsapp_views.whatsapp_monitoring_list, name='whatsapp_monitoring_list'),
    path('whatsapp/monitoring/retry/', whatsapp_views.retry_failed_notifications, name='whatsapp_retry_failed'),
]
```

#### Agent Mali - URLs à ajouter :
```python
# agent_mali_app/urls.py
from .whatsapp_integration import whatsapp_monitoring_dashboard, whatsapp_monitoring_list, retry_failed_notifications

urlpatterns += [
    path('whatsapp/monitoring/', whatsapp_monitoring_dashboard, name='whatsapp_monitoring'),
    path('whatsapp/monitoring/list/', whatsapp_monitoring_list, name='whatsapp_monitoring_list'), 
    path('whatsapp/monitoring/retry/', retry_failed_notifications, name='whatsapp_retry_failed'),
]
```

## 📊 Dashboard de Monitoring

### Vue spécifique par app (agent_chine, agent_mali) :
- Statistiques filtrées par `source_app`
- Taux de succès spécifique
- Relance des échecs pour l'app uniquement
- Interface adaptée au contexte de l'app

### Vue admin complète :
- Toutes les notifications de toutes les apps
- Statistiques globales et par app
- Gestion centralisée des retries
- Vue d'ensemble du système

## 🔄 Tâches Celery

### Configuration Celery Beat (optionnelle) :
```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'process-whatsapp-retries-every-5-minutes': {
        'task': 'whatsapp_monitoring_app.tasks.process_whatsapp_retries_task',
        'schedule': 300.0,  # 5 minutes
    },
    'cleanup-old-whatsapp-attempts-daily': {
        'task': 'whatsapp_monitoring_app.tasks.cleanup_old_whatsapp_attempts',
        'schedule': crontab(hour=2, minute=0),  # 2h du matin
    },
}
```

### Tâches disponibles :
1. **`send_whatsapp_notification_async`** - Envoyer notification WhatsApp
2. **`process_whatsapp_retries_task`** - Traiter les retries
3. **`cleanup_old_whatsapp_attempts`** - Nettoyer anciennes tentatives
4. **`create_client_account_async`** - Créer client avec notifications
5. **`send_bulk_whatsapp_notifications`** - Envoi en masse

## 🛠️ Instructions de Déploiement

### 1. Migrations
```bash
python manage.py makemigrations whatsapp_monitoring_app
python manage.py migrate
```

### 2. Démarrer Celery Worker
```bash
# Worker principal
celery -A ts_air_cargo worker -l info

# Worker avec Beat pour tâches périodiques (optionnel)
celery -A ts_air_cargo worker -B -l info
```

### 3. Monitoring Celery (optionnel)
```bash
# Flower pour monitoring Celery
pip install flower
celery -A ts_air_cargo flower
# Accessible sur http://localhost:5555
```

## 📝 Templates à Créer

### Pour chaque app, créer les templates :

#### agent_chine_app/templates/agent_chine_app/ :
- `whatsapp_monitoring.html` (déjà créé)
- `whatsapp_monitoring_list.html`
- `whatsapp_attempt_details.html`

#### agent_mali_app/templates/agent_mali_app/ :
- `whatsapp_monitoring.html` (copier depuis agent_chine et adapter)
- `whatsapp_monitoring_list.html`
- `whatsapp_attempt_details.html`

#### admin_chine_app/templates/admin_chine_app/ :
- Utiliser les vues de `whatsapp_monitoring_app` (monitoring complet)

#### admin_mali_app/templates/admin_mali_app/ :
- Utiliser les vues de `whatsapp_monitoring_app` (monitoring complet)

## 🔧 Configuration des Apps

### Settings.py - Apps installées :
```python
INSTALLED_APPS = [
    # ... autres apps
    'whatsapp_monitoring_app',  # IMPORTANT : Ajouter cette ligne
    'agent_chine_app',
    'agent_mali_app',
    'admin_chine_app',
    'admin_mali_app',
]
```

## 📈 Exemples d'Usage

### 1. Notification de création de colis :
```python
# Dans agent_chine_app
from whatsapp_monitoring_app.tasks import send_whatsapp_async

def notify_colis_created(colis):
    message = f"📦 Nouveau colis {colis.numero_suivi} créé pour {colis.client.user.get_full_name()}"
    
    task = send_whatsapp_async(
        user=colis.client.user,
        message_content=message,
        source_app='agent_chine',
        message_type='colis_creation',
        category='colis_management',
        title='Nouveau colis créé',
        priority=3
    )
    
    return task
```

### 2. Notification d'arrivée au Mali :
```python
# Dans agent_mali_app
from .whatsapp_integration import send_whatsapp_notification_mali

def notify_colis_arrival_mali(colis):
    message = f"🎉 Votre colis {colis.numero_suivi} est arrivé au Mali! Venez le récupérer."
    
    task = send_whatsapp_notification_mali(
        user=colis.client.user,
        message_content=message,
        message_type='delivery',
        category='colis_arrival',
        title='Arrivée colis Mali',
        priority=1  # Haute priorité
    )
    
    return task
```

### 3. Création de client depuis une API :
```python
# Vue API dans agent_chine_app
from .client_async_utils import create_client_for_view

@require_http_methods(["POST"])
def create_client_api(request):
    try:
        data = json.loads(request.body)
        
        result = create_client_for_view(
            request=request,
            telephone=data['telephone'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email')
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
```

## 🎯 Points Clés

1. **Séparation claire** : Chaque app voit seulement ses notifications
2. **Monitoring centralisé** : Base de données commune dans `whatsapp_monitoring_app`
3. **Asynchrone** : Toutes les notifications et créations de clients via Celery
4. **Évolutif** : Facile d'ajouter de nouvelles apps au système
5. **Admin complet** : Les apps admin voient tout le monitoring
6. **Retry automatique** : Gestion intelligente des échecs avec backoff exponentiel

## 🔍 Monitoring et Debug

### Vérifier le statut d'une tâche :
```python
from agent_chine_app.client_async_utils import get_client_creation_status

status = get_client_creation_status(task_id)
print(f"Status: {status['status']}")
print(f"Result: {status['result']}")
```

### Consulter les logs Celery :
```bash
# Logs détaillés
celery -A ts_air_cargo worker -l debug

# Logs en temps réel
celery -A ts_air_cargo events
```

### Dashboard Web (si Flower installé) :
- URL : http://localhost:5555
- Vue des tâches en cours
- Statistiques de performance
- Retry manuel des tâches échouées

---

🎉 **Le système est maintenant prêt à être utilisé !**

Chaque app peut envoyer des notifications de manière asynchrone et surveiller ses propres notifications, while l'admin a une vue d'ensemble complète du système.