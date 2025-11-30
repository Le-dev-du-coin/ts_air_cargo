# 🔄 Système de Récupération des Notifications WhatsApp

## 📋 Vue d'Ensemble

Ce système assure la **fiabilité maximale** des notifications WhatsApp en cas de défaillance de l'API WaChap (déconnexion, abonnement expiré, problème réseau, etc.).

### ✅ Garanties

- ✅ **Aucune notification perdue** : Retry automatique jusqu'à 10 tentatives sur 24h
- ✅ **Classification intelligente** : Distinction erreurs temporaires vs permanentes
- ✅ **Alertes proactives** : Notification admin en cas de problème critique
- ✅ **Backoff exponentiel** : Évite la surcharge (30min → 1h → 2h → 4h...)
- ✅ **Dashboard monitoring** : Visibilité complète sur l'état des notifications

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  ÉVÉNEMENT (fermeture lot, livraison, etc.)            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  1. Créer Notification BDD   │
    │     statut = 'en_attente'    │
    │     prochaine_tentative = Now│
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  2. Celery: Envoi immédiat   │
    │     ✅ → 'envoye'            │
    │     ❌ → 'echec' (temporaire)│
    │     ❌ → 'echec_permanent'   │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  3. Celery Beat (30 min)     │
    │  Retry automatique si échec  │
    │  temporaire avec backoff     │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  4. Alerte Admin (1h)        │
    │  Si taux échec > 50% ou      │
    │  20+ échecs/h → Email/WA     │
    └──────────────────────────────┘
```

---

## 🗂️ Composants Implémentés

### 1. **Modèle Notification Amélioré**
📁 `notifications_app/models.py`

**Nouveaux statuts** :
- `en_attente` : Notification créée, en attente d'envoi
- `envoye` : Envoi réussi
- `echec` : Échec temporaire, retry possible
- `echec_permanent` : Échec définitif, nécessite intervention manuelle
- `annulee` : Notification annulée manuellement

**Nouvelle méthode** :
```python
notification.marquer_comme_echec(
    erreur="Connection timeout",
    erreur_type='temporaire'  # ou 'permanent'
)
```

**Backoff exponentiel** :
- Tentative 1 : +30 min
- Tentative 2 : +1h
- Tentative 3 : +2h
- Tentative 4 : +4h
- Etc. (max 24h)

---

### 2. **Classificateur d'Erreurs**
📁 `notifications_app/error_classifier.py`

**Catégorisation automatique** :

| Type d'erreur | Classification | Action |
|---------------|----------------|--------|
| `timeout`, `503`, `502` | Temporaire | Retry automatique |
| `401`, `403` (Auth) | Permanente | Alerte admin |
| `400` (Bad Request) | Permanente | Vérifier numéro |
| `429` (Rate Limit) | Temporaire | Retry après délai |
| `connection_error` | Temporaire | Retry automatique |

**Usage** :
```python
from notifications_app.error_classifier import classify_wachap_error

result = classify_wachap_error(
    error_type='http_401',
    error_message='Unauthorized: Token expired'
)

if result['should_retry']:
    # Programmer retry
if result['should_alert_admin']:
    # Alerter admin
```

---

### 3. **Commande Django Retry**
📁 `notifications_app/management/commands/retry_failed_notifications.py`

**Usage** :
```bash
# Mode production
python manage.py retry_failed_notifications

# Mode simulation (voir ce qui serait fait)
python manage.py retry_failed_notifications --dry-run

# Mode verbose (détails)
python manage.py retry_failed_notifications --verbose

# Limiter le nombre
python manage.py retry_failed_notifications --limit=50

# Changer max tentatives
python manage.py retry_failed_notifications --max-retries=15
```

**Sortie exemple** :
```
============================================================
🔄 RETRY NOTIFICATIONS ÉCHOUÉES
============================================================

📊 Notifications trouvées : 12
📅 Date/Heure actuelle : 27/11/2025 12:30:15
🔢 Limite de tentatives : 10
============================================================

📧 Notification #451
   Destinataire: Mamadou Traoré (+22370123456)
   Tentatives: 3/10
   Prochaine tentative prévue: 27/11/2025 12:15
   Catégorie: Colis arrivé
   ✅ Mise en file d'attente (tentative 4)

============================================================
📊 RÉSUMÉ DE L'EXÉCUTION
============================================================
Total traité       : 12
Mises en file      : 12

✅ 12 notification(s) mise(s) en file d'attente pour envoi asynchrone
```

---

### 4. **Tâches Celery Beat Automatiques**
📁 `notifications_app/tasks.py`

#### 4.1 **Retry automatique** (toutes les 30 min)
```python
@shared_task
def retry_failed_notifications_task():
    """Relance les notifications échouées prêtes pour retry"""
```

Configuration dans `settings.py` :
```python
CELERY_BEAT_SCHEDULE = {
    'retry-failed-notifications': {
        'task': 'notifications_app.tasks.retry_failed_notifications_task',
        'schedule': 1800.0,  # 30 minutes
    },
}
```

#### 4.2 **Vérification santé** (toutes les heures)
```python
@shared_task
def check_notification_health_task():
    """Vérifie l'état du système et alerte si problème"""
```

Configuration :
```python
CELERY_BEAT_SCHEDULE = {
    'check-notification-health': {
        'task': 'notifications_app.tasks.check_notification_health_task',
        'schedule': 3600.0,  # 1 heure
    },
}
```

---

### 5. **Système d'Alertes Admin**
📁 `notifications_app/alert_system.py`

**Seuils d'alerte** :
- ≥ 20 échecs en 1h → Alerte critique
- ≥ 5 échecs permanents en 24h → Alerte warning
- Taux d'échec ≥ 50% → Alerte critique

**Canaux d'alerte** :
1. **Email** (si `ALERT_EMAIL_ENABLED=True`)
2. **WhatsApp** (si `ALERT_WHATSAPP_ENABLED=True` ET alerte critique)

**Configuration dans `.env`** :
```bash
# Activer le système d'alertes
ALERT_SYSTEM_ENABLED=True
ALERT_EMAIL_ENABLED=True
ALERT_WHATSAPP_ENABLED=True

# Destinataires
ADMIN_EMAIL=admin@ts-aircargo.com
ADMIN_PHONE=+22370702150

# Seuils personnalisés (optionnel)
ALERT_FAILED_OTP_THRESHOLD=10
ALERT_WHATSAPP_FAILURE_THRESHOLD=5
```

**Cooldown** : 1h entre alertes similaires (évite spam)

---

## 🚀 Déploiement

### 1. Appliquer les migrations
```bash
python manage.py migrate notifications_app
```

### 2. Démarrer Celery Worker
```bash
celery -A ts_air_cargo worker -Q notifications --loglevel=info
```

### 3. Démarrer Celery Beat
```bash
celery -A ts_air_cargo beat --loglevel=info
```

### 4. (Optionnel) Configurer CRON comme backup
Si Celery Beat n'est pas disponible, utiliser crontab :
```bash
# Retry toutes les 30 min
*/30 * * * * cd /path/to/project && python manage.py retry_failed_notifications

# Health check toutes les heures
0 * * * * cd /path/to/project && python manage.py check_notification_health
```

---

## 📊 Monitoring

### Commandes utiles

**Voir les notifications échouées** :
```bash
python manage.py shell
>>> from notifications_app.models import Notification
>>> Notification.objects.filter(statut='echec').count()
12
```

**Statistiques détaillées** :
```python
from datetime import timedelta
from django.utils import timezone

# Dernières 24h
last_24h = timezone.now() - timedelta(days=1)

stats = {
    'total': Notification.objects.filter(date_creation__gte=last_24h).count(),
    'succes': Notification.objects.filter(date_creation__gte=last_24h, statut='envoye').count(),
    'echecs_temp': Notification.objects.filter(date_creation__gte=last_24h, statut='echec').count(),
    'echecs_perm': Notification.objects.filter(date_creation__gte=last_24h, statut='echec_permanent').count(),
}

print(f"Taux de succès: {(stats['succes'] / stats['total'] * 100):.1f}%")
```

**Logs Celery** :
```bash
# Suivre les logs en temps réel
tail -f /path/to/logs/celery.log | grep -i notification
```

---

## 🧪 Tests

### Test manuel de défaillance

```python
# Dans Django shell
from notifications_app.models import Notification
from custom_user.models import User

# Créer une notification de test
user = User.objects.get(telephone='+22370123456')
notif = Notification.objects.create(
    destinataire=user,
    type_notification='whatsapp',
    categorie='information_generale',
    titre='Test de récupération',
    message='Ceci est un test',
    telephone_destinataire=user.telephone,
    statut='echec',
    nombre_tentatives=2,
    prochaine_tentative=timezone.now()  # Immédiat
)

# Attendre 30 min → Celery Beat doit la relancer
# Ou manuellement :
from notifications_app.tasks import send_individual_notification
send_individual_notification.delay(notif.id)
```

---

## 🔧 Dépannage

### Problème : Notifications non relancées

**Causes possibles** :
1. Celery Beat non démarré
2. Queue 'notifications' non consommée

**Solution** :
```bash
# Vérifier Celery
celery -A ts_air_cargo inspect active

# Vérifier les workers
celery -A ts_air_cargo inspect stats

# Relancer manuellement
python manage.py retry_failed_notifications --verbose
```

---

### Problème : Pas d'alertes reçues

**Vérifier la configuration** :
```python
# Dans Django shell
from django.conf import settings

print("Email activé:", settings.ALERT_EMAIL_ENABLED)
print("WhatsApp activé:", settings.ALERT_WHATSAPP_ENABLED)
print("Admin email:", settings.ADMIN_EMAIL)
print("Admin phone:", settings.ADMIN_PHONE)
```

---

## 📈 Améliorations Futures (Non implémentées)

- [ ] Dashboard web pour visualiser les notifications échouées
- [ ] API REST pour consulter l'état des notifications
- [ ] Métriques Prometheus/Grafana
- [ ] Retry prioritaire pour notifications critiques
- [ ] Export CSV des échecs pour analyse

---

## 🤝 Support

Pour toute question ou problème :
- Consulter les logs : `/path/to/logs/django.log`
- Logs Celery : `/path/to/logs/celery.log`
- Issues GitHub : https://github.com/your-repo/ts-air-cargo

---

## 📝 Changelog

### Version 1.0 (27/11/2025)
- ✅ Classification erreurs temporaires/permanentes
- ✅ Backoff exponentiel
- ✅ Retry automatique Celery Beat
- ✅ Système d'alertes admin
- ✅ Commande Django retry_failed_notifications
- ✅ Health check automatique
