# Système de Monitoring WhatsApp - Agent Chine App

Ce document décrit le système de monitoring et retry automatique des notifications WhatsApp implémenté dans l'application `agent_chine_app`.

## 📋 Vue d'ensemble

Le système de monitoring WhatsApp permet de :
- ✅ Tracker toutes les tentatives d'envoi de notifications WhatsApp
- 🔄 Relancer automatiquement les messages échoués (retry)
- 📊 Monitorer les performances et la fiabilité des envois
- 🛠️ Gérer manuellement les tentatives depuis l'interface d'administration
- 📈 Analyser les statistiques d'envoi

## 🏗️ Architecture

### Modèles principaux

#### `WhatsAppMessageAttempt`
- **Rôle** : Suivi des tentatives d'envoi de messages
- **Fichier** : `agent_chine_app/models/whatsapp_monitoring.py`
- **Fonctionnalités** :
  - Gestion des statuts (pending, sending, sent, delivered, failed, etc.)
  - Système de retry avec délai exponentiel
  - Priorités de messages
  - Métadonnées complètes (provider ID, erreurs, contexte)

#### `WhatsAppWebhookLog`
- **Rôle** : Log des webhooks reçus des providers
- **Fonctionnalités** :
  - Traçage des confirmations de livraison
  - Mise à jour automatique du statut des tentatives

### Services

#### `WhatsAppMonitoringService`
- **Fichier** : `agent_chine_app/services/whatsapp_monitoring.py`
- **Méthodes principales** :
  - `send_monitored_notification()` : Interface principale d'envoi
  - `process_pending_retries()` : Traitement des messages en attente
  - `get_monitoring_stats()` : Récupération des statistiques

#### `WhatsAppRetryTask`
- **Rôle** : Tâches de maintenance (retry, nettoyage)
- **Méthodes** :
  - `run_retry_task()` : Exécution des retries
  - `cleanup_old_attempts()` : Nettoyage des anciennes tentatives

## 🚀 Utilisation

### Envoi d'une notification avec monitoring

```python
from agent_chine_app.services.whatsapp_monitoring import WhatsAppMonitoringService

# Envoi simple avec monitoring
attempt, success, error_message = WhatsAppMonitoringService.send_monitored_notification(
    user=user,
    message_content="Votre message ici",
    message_type='notification',  # 'account', 'otp', 'system', etc.
    category='creation_compte',
    title='Titre du message',
    priority=2,  # 1=très haute, 5=très basse
    max_attempts=3,
    region_override='chine'  # Force l'instance Chine
)

if success:
    print(f"Message envoyé ! ID: {attempt.id}")
else:
    print(f"Message en retry: {error_message}")
```

### Traitement des retries

```python
# Traitement automatique des retries
stats = WhatsAppMonitoringService.process_pending_retries(max_retries_per_run=50)
print(f"Traité: {stats['processed']}, Succès: {stats['success']}")
```

### Statistiques

```python
# Récupération des statistiques
stats = WhatsAppMonitoringService.get_monitoring_stats(days_back=7)
print(f"Taux de succès: {stats['success_rate']:.1f}%")
```

## 🖥️ Interface d'administration

### URLs disponibles

- `/agent-chine/whatsapp/dashboard/` : Dashboard principal
- `/agent-chine/whatsapp/attempts/` : Liste des tentatives
- `/agent-chine/whatsapp/attempts/<id>/` : Détail d'une tentative
- `/agent-chine/whatsapp/webhook/` : Endpoint pour webhooks
- `/agent-chine/whatsapp/admin/cleanup/` : Administration et nettoyage

### Actions disponibles

- **Retry manuel** : Relancer une tentative spécifique
- **Annulation** : Annuler une tentative en attente
- **Retry en lot** : Traiter tous les messages en attente
- **Nettoyage** : Supprimer les anciennes tentatives

## ⚙️ Configuration

### Types de messages
- `account` : Création de comptes
- `otp` : Codes d'authentification
- `system` : Messages système
- `notification` : Notifications générales
- `urgent` : Notifications urgentes
- `colis_status` : Statut de colis
- `lot_status` : Statut de lots

### Priorités
1. **Très haute** : Messages critiques (OTP, comptes)
2. **Haute** : Notifications importantes
3. **Normale** : Messages standards (défaut)
4. **Basse** : Notifications non-urgentes
5. **Très basse** : Messages marketing

### Stratégie de retry
- **Délai exponentiel** : base_delay × (2^attempt_count)
- **Délai de base** : 5 minutes (configurable)
- **Maximum d'attente** : 32 × délai de base
- **Tentatives par défaut** : 3 (configurable par message)

## 🔧 Commandes Django

### Traitement des retries
```bash
# Traitement normal
python manage.py process_whatsapp_retries

# Simulation (dry-run)
python manage.py process_whatsapp_retries --dry-run

# Avec nettoyage
python manage.py process_whatsapp_retries --cleanup

# Verbose
python manage.py process_whatsapp_retries --verbose --max-retries 100
```

### Options disponibles
- `--max-retries` : Nombre max de messages à traiter (défaut: 50)
- `--cleanup` : Nettoyer les anciennes tentatives
- `--cleanup-days` : Âge en jours pour le nettoyage (défaut: 30)
- `--dry-run` : Simulation sans envoi
- `--verbose` : Affichage détaillé

## 🕐 Automatisation (Cron)

### Configuration recommandée

```bash
# Traitement des retries toutes les 5 minutes
*/5 * * * * cd /path/to/project && python manage.py process_whatsapp_retries --max-retries 100

# Nettoyage quotidien à 2h du matin
0 2 * * * cd /path/to/project && python manage.py process_whatsapp_retries --cleanup --cleanup-days 30
```

### Fonction utilitaire
```python
# Pour intégration avec Celery ou autres systèmes
from agent_chine_app.management.commands.process_whatsapp_retries import run_whatsapp_retries

# Exécution simple
stats = run_whatsapp_retries()
```

## 📊 Monitoring et alertes

### Métriques importantes
- **Taux de succès** : Pourcentage de messages envoyés avec succès
- **Délai moyen** : Temps entre création et envoi
- **Messages en attente** : Nombre de retries programmés
- **Échecs définitifs** : Messages abandonnés après max_attempts

### Alertes recommandées
- Taux de succès < 90% sur 1h
- Plus de 100 messages en attente de retry
- Échecs définitifs > 5% sur 24h
- Délai moyen > 30 minutes

## 🔍 Dépannage

### Vérifications courantes

```python
# Vérifier les messages en attente
from agent_chine_app.models.whatsapp_monitoring import WhatsAppMessageAttempt

pending = WhatsAppMessageAttempt.objects.filter(status='failed_retry').count()
print(f"Messages en attente: {pending}")

# Messages prêts pour retry maintenant
ready_now = WhatsAppMessageAttempt.get_pending_retries().count()
print(f"Prêts pour retry: {ready_now}")

# Dernières erreurs
recent_failures = WhatsAppMessageAttempt.objects.filter(
    status='failed_final'
).order_by('-last_attempt_at')[:5]

for attempt in recent_failures:
    print(f"Erreur: {attempt.error_message}")
```

### Problèmes fréquents

1. **Messages bloqués en "sending"**
   - Cause : Processus interrompu pendant l'envoi
   - Solution : Reset manuel du statut ou retry

2. **Trop de retries en attente**
   - Cause : Provider indisponible longtemps
   - Solution : Ajuster max_attempts ou délais

3. **Webhooks non traités**
   - Cause : Endpoint webhook non accessible
   - Solution : Vérifier la configuration réseau

## 🛡️ Sécurité

### Webhook endpoint
- Endpoint public : `/agent-chine/whatsapp/webhook/`
- Validation recommandée : Signature HMAC (à implémenter)
- Rate limiting : Recommandé

### Données sensibles
- Les mots de passe temporaires sont loggés dans `message_content`
- Considérer le chiffrement pour les messages sensibles
- Nettoyage automatique des anciens messages

## 📈 Évolutions futures

### Améliorations possibles
1. **Chiffrement des messages sensibles**
2. **Validation des webhooks par signature**
3. **Interface graphique avancée avec graphiques**
4. **Intégration avec systèmes d'alerting (Slack, Email)**
5. **API REST pour monitoring externe**
6. **Support de multiples providers WhatsApp**

### Intégrations
- **Celery** : Traitement asynchrone des retries
- **Redis** : Cache pour améliorer les performances
- **Prometheus** : Métriques pour monitoring avancé
- **Grafana** : Dashboards visuels

## 📞 Support

Pour toute question ou problème concernant le système de monitoring WhatsApp :

1. Vérifier les logs Django
2. Utiliser les commandes de diagnostic
3. Consulter le dashboard de monitoring
4. Examiner les tentatives échouées pour identifier les patterns

## 🏷️ Version

- **Version** : 1.0.0
- **Date** : Septembre 2025
- **Compatibilité** : Django 5.2+, Python 3.8+