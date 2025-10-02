# 📚 DEVBOOK - CORRECTION NOTIFICATIONS WHATSAPP TS AIR CARGO

## 🎯 OBJECTIF
Corriger les échecs d'envoi des notifications WhatsApp lors de la création de clients dans l'app agent Chine.

## 🔍 PROBLÈMES IDENTIFIÉS
1. **Notifications désactivées** dans le code de création client
2. **Erreurs de parsing** des réponses API WaChap
3. **Timeouts excessifs** (30s)
4. **Gestion des réponses non-standard** de l'API

## 📋 CHECKLIST DES CORRECTIONS

### ✅ **ÉTAPE 1 : Setup environnement local**

```bash
# 1. Cloner ou récupérer le code depuis le serveur
git pull origin main  # ou la branche appropriée

# 2. Activer l'environnement virtuel
source venv/bin/activate  # ou .venv/bin/activate selon votre setup

# 3. Installer les dépendances si nécessaire
pip install -r requirements.txt

# 4. Configurer les variables d'environnement pour les tests
# Créer un fichier .env.local avec des valeurs de test
cp .env .env.local
```

### ✅ **ÉTAPE 2 : CORRECTION PRINCIPALE - Réactiver les notifications**

**Fichier à modifier :** `agent_chine_app/client_management.py`

**Localiser les lignes ~174-176 :**
```python
# Les notifications sont gérées par Celery dans une tâche séparée
notification_sent = False  # Pas de notification dans cette version synchrone
logger.info(f"✅ Compte client créé: {telephone} (notifications gérées par Celery)")
```

**Remplacer par :**
```python
# Envoyer la notification de création de compte
try:
    from notifications_app.services import NotificationService
    notification_sent = NotificationService.send_client_creation_notification(
        user=user,
        password=final_password,
        sender_role='agent_chine'
    )
    if notification_sent:
        logger.info(f"✅ Notification envoyée pour {telephone}")
    else:
        logger.warning(f"⚠️ Échec envoi notification pour {telephone}")
except Exception as e:
    logger.error(f"❌ Erreur envoi notification pour {telephone}: {str(e)}")
    notification_sent = False
```

**Faire la même correction aux lignes ~77-79 (autre méthode) :**
```python
# Chercher et remplacer la même séquence dans get_or_create_client()
```

### ✅ **ÉTAPE 3 : CORRECTION - Améliorer le parsing des réponses API**

**Fichier à modifier :** `notifications_app/wachap_service.py`

**Localiser la ligne ~331 et les suivantes :**
```python
top_status = str(response_data.get('status', '')).lower()
nested_status = ''
if isinstance(response_data.get('message'), dict):
    nested_status = str(response_data['message'].get('status', '')).lower()
```

**Remplacer par :**
```python
# Vérification de type pour éviter l'erreur 'list' object has no attribute 'get'
if isinstance(response_data, dict):
    top_status = str(response_data.get('status', '')).lower()
    nested_status = ''
    message_data = response_data.get('message')
    if isinstance(message_data, dict):
        nested_status = str(message_data.get('status', '')).lower()
elif isinstance(response_data, list):
    # Cas où l'API retourne une liste au lieu d'un dict
    top_status = ''
    nested_status = ''
    if response_data and isinstance(response_data[0], dict):
        top_status = str(response_data[0].get('status', '')).lower()
    logger.warning(f"API WaChap a retourné une liste au lieu d'un dict: {response_data}")
else:
    top_status = ''
    nested_status = ''
    logger.error(f"Réponse API WaChap de type inattendu: {type(response_data)} - {response_data}")
```

**Et corriger l'extraction du message_id (lignes ~338-342) :**
```python
# Extraire l'ID du message avec vérification de type
message_id = None
if isinstance(response_data, dict):
    message_id = (
        response_data.get('id') or
        response_data.get('message_id') or
        (response_data.get('message', {}).get('key', {}).get('id') 
         if isinstance(response_data.get('message'), dict) else None)
    )
elif isinstance(response_data, list) and response_data:
    if isinstance(response_data[0], dict):
        message_id = response_data[0].get('id') or response_data[0].get('message_id')
```

### ✅ **ÉTAPE 4 : CORRECTION - Réduire les timeouts**

**Fichier à modifier :** `notifications_app/wachap_service.py`

**Localiser toutes les occurrences de `timeout=30` (lignes 314, 490, 534, 572) :**
```python
timeout=30
```

**Remplacer par :**
```python
timeout=15  # Réduction de 30s à 15s pour détecter plus vite les problèmes
```

### ✅ **ÉTAPE 5 : AMÉLIORATION - Meilleure gestion des erreurs**

**Fichier à modifier :** `notifications_app/wachap_service.py`

**Localiser la méthode d'gestion des erreurs et ajouter après la ligne de timeout :**
```python
except requests.exceptions.Timeout:
    timeout_msg = f"Timeout WaChap {region} pour {formatted_phone}"
    if attempt_id:
        wachap_monitor.record_message_error(attempt_id, 'timeout', timeout_msg, 15.0)
    logger.error(timeout_msg)
    return False, timeout_msg, None
except requests.exceptions.RequestException as e:
    # Nouvelles erreurs à gérer
    connection_msg = f"Erreur connexion WaChap {region} pour {formatted_phone}: {str(e)}"
    if attempt_id:
        wachap_monitor.record_message_error(attempt_id, 'connection_error', connection_msg, 0)
    logger.error(connection_msg)
    return False, connection_msg, None
```

### ✅ **ÉTAPE 6 : TESTS DE VALIDATION**

**Créer un fichier de test :** `test_notification_fix.py`

```python
#!/usr/bin/env python
"""
Script de test pour valider les corrections des notifications WhatsApp
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from agent_chine_app.client_management import ClientAccountManager
from notifications_app.models import Notification
from notifications_app.services import NotificationService

def test_client_creation_notification():
    """Test la création d'un client et l'envoi de notification"""
    print("🧪 Test création client avec notification...")
    
    # Numéro de test (utilisez un numéro qui ne spam pas de vrais clients)
    test_phone = "+22300000001"  # Numéro fictif pour test
    
    try:
        # Supprimer le client de test s'il existe
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(telephone=test_phone).delete()
        
        # Créer le client avec notification
        result = ClientAccountManager.get_or_create_client_with_password(
            telephone=test_phone,
            first_name="Test",
            last_name="Client",
            email="test@example.com",
            password="test123456",
            notify=True
        )
        
        print(f"✅ Client créé: {result['created']}")
        print(f"✅ Notification envoyée: {result['notification_sent']}")
        
        # Vérifier qu'une notification a été créée en base
        notifications = Notification.objects.filter(telephone_destinataire=test_phone)
        print(f"✅ Notifications en base: {notifications.count()}")
        
        if notifications.exists():
            notif = notifications.first()
            print(f"✅ Statut notification: {notif.statut}")
            print(f"✅ Message: {notif.message[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test: {str(e)}")
        return False

def test_wachap_response_parsing():
    """Test le parsing des réponses WaChap"""
    print("🧪 Test parsing réponses API...")
    
    from notifications_app.wachap_service import WaChapService
    service = WaChapService()
    
    # Test avec dict normal
    dict_response = {'status': 'success', 'id': '12345'}
    print(f"✅ Test dict: {isinstance(dict_response, dict)}")
    
    # Test avec liste (cas d'erreur)
    list_response = [{'status': 'success', 'id': '12345'}]
    print(f"✅ Test liste: {isinstance(list_response, list)}")
    
    return True

if __name__ == "__main__":
    print("🚀 Démarrage des tests de validation...")
    
    success = True
    success &= test_client_creation_notification()
    success &= test_wachap_response_parsing()
    
    if success:
        print("✅ Tous les tests ont réussi!")
    else:
        print("❌ Certains tests ont échoué")
    
    sys.exit(0 if success else 1)
```

### ✅ **ÉTAPE 7 : COMMANDES DE TEST**

```bash
# 1. Lancer les tests unitaires Django
python manage.py test notifications_app

# 2. Lancer le script de test personnalisé
python test_notification_fix.py

# 3. Tester la création d'un client via shell Django
python manage.py shell -c "
from agent_chine_app.client_management import ClientAccountManager
result = ClientAccountManager.get_or_create_client_with_password('+22300000002', 'Test', 'User', notify=True)
print('Résultat:', result)
"

# 4. Vérifier les notifications créées
python manage.py shell -c "
from notifications_app.models import Notification
from datetime import datetime, timedelta
recent_notifications = Notification.objects.filter(date_creation__gte=datetime.now() - timedelta(hours=1))
print(f'Notifications récentes: {recent_notifications.count()}')
for n in recent_notifications:
    print(f'  - {n.telephone_destinataire}: {n.statut}')
"
```

### ✅ **ÉTAPE 8 : VALIDATION DU FONCTIONNEMENT**

**Signes que les corrections fonctionnent :**

1. **Création de notifications en base :**
   ```sql
   -- Requête pour vérifier
   SELECT COUNT(*) FROM notifications_app_notification 
   WHERE date_creation >= NOW() - INTERVAL '1 HOUR';
   ```

2. **Logs positifs :**
   ```
   INFO: ✅ Notification envoyée pour +22300000001
   INFO: Notification 123 envoyée avec succès à +22300000001
   ```

3. **Pas d'erreurs de parsing :**
   ```
   # Plus de: ERROR: 'list' object has no attribute 'get'
   ```

4. **Timeouts plus rapides :**
   ```
   # Timeouts en 15s au lieu de 30s
   ```

### ✅ **ÉTAPE 9 : DÉPLOIEMENT EN PRODUCTION**

```bash
# 1. Commit des changements
git add .
git commit -m "fix: Réactivation des notifications WhatsApp pour création clients

- Réactivé l'envoi de notifications dans client_management.py
- Amélioré le parsing des réponses API WaChap
- Réduit les timeouts de 30s à 15s
- Ajouté gestion des réponses non-standard de l'API

Fixes #[numero_issue] - 60 échecs notifications WhatsApp"

# 2. Push vers le repository
git push origin [votre-branche]

# 3. Sur le serveur de production, après merge :
cd /var/www/ts_air_cargo
git pull origin main
sudo systemctl restart ts-air-cargo  # ou votre service
sudo systemctl restart celery-worker  # redémarrer Celery
```

### ✅ **ÉTAPE 10 : MONITORING POST-DÉPLOIEMENT**

```bash
# 1. Surveiller les logs après déploiement
tail -f /var/www/ts_air_cargo/logs/django.log | grep -i notification

# 2. Vérifier les statistiques de notifications
python manage.py shell -c "
from notifications_app.models import Notification
from datetime import datetime, timedelta
recent = Notification.objects.filter(date_creation__gte=datetime.now() - timedelta(hours=1))
print(f'Succès: {recent.filter(statut=\"envoye\").count()}')
print(f'Échecs: {recent.filter(statut=\"echec\").count()}')
"

# 3. Tester la création d'un vrai client (avec précaution)
# Utiliser un numéro de test ou votre propre numéro
```

## 🎯 **RÉSULTAT ATTENDU**

Après ces corrections :
- ✅ Création de clients → Notification automatique
- ✅ Messages WhatsApp envoyés aux nouveaux clients
- ✅ Réduction des timeouts et erreurs
- ✅ Meilleure stabilité du système
- ✅ Monitoring amélioré

## 📞 **SUPPORT**

Si vous rencontrez des problèmes :
1. Vérifiez les logs Django et Celery
2. Testez d'abord avec des numéros fictifs
3. Validez chaque étape avant de passer à la suivante
4. En cas de doute, revert les changements et recommencez

**Temps estimé :** 2-3 heures pour l'implémentation complète et les tests.

## 📋 **RÉSUMÉ DU DIAGNOSTIC**

### Problème principal identifié :
- **Notifications complètement désactivées** dans le code de création clients
- Les 60 échecs correspondent à des tentatives qui n'ont jamais été lancées

### Causes secondaires :
- Timeouts excessifs (30s)
- Parsing API défaillant pour certaines réponses
- Gestion d'erreurs incomplète

### Impact :
- 204 notifications depuis le 1er octobre
- 165 réussies (81%) - 39 échecs (19%)
- **MAIS** : les nouvelles créations de clients ne génèrent AUCUNE notification

### Solution :
Réactivation complète du système de notification + améliorations robustesse.
