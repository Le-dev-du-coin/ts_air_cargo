# ✅ Configuration Orange SMS - Résumé

## Problème résolu

Le bouton "RMP par SMS" affichait une erreur indiquant que les credentials n'étaient pas configurés, alors qu'ils étaient présents dans le fichier `.env`.

### Causes identifiées

1. **Commentaires inline dans `.env`** : Les variables `ORANGE_SMS_USE_SENDER_NAME` et `ORANGE_SMS_USE_SANDBOX` contenaient des commentaires après la valeur (ex: `True  # False pour production`), ce qui empêchait `python-dotenv` de les parser correctement.

2. **Variables manquantes dans `settings.py`** : Les variables d'environnement Orange SMS n'étaient pas déclarées dans `ts_air_cargo/settings.py`, donc Django ne les chargeait pas.

3. **Problème cryptography avec xhtml2pdf** : Un conflit de versions entre `cryptography 46.0.3` et `pyhanko-certvalidator` empêchait le serveur de démarrer.

## Solutions appliquées

### 1. Correction du fichier `.env`

**Avant :**
```env
ORANGE_SMS_USE_SENDER_NAME=False  # True après validation
ORANGE_SMS_USE_SANDBOX=True  # False pour production
```

**Après :**
```env
# True après validation
ORANGE_SMS_USE_SENDER_NAME=False

# Environnement (False pour production)
ORANGE_SMS_USE_SANDBOX=True
```

### 2. Ajout des variables dans `settings.py`

Ajouté dans `/ts_air_cargo/settings.py` (après ligne 201) :

```python
# === ORANGE SMS API CONFIGURATION ===
# Credentials OAuth2 (REQUIS)
ORANGE_SMS_CLIENT_ID = os.getenv('ORANGE_SMS_CLIENT_ID', '')
ORANGE_SMS_CLIENT_SECRET = os.getenv('ORANGE_SMS_CLIENT_SECRET', '')

# Sender Configuration
ORANGE_SMS_SENDER_PHONE = os.getenv('ORANGE_SMS_SENDER_PHONE', '')
ORANGE_SMS_SENDER_NAME = os.getenv('ORANGE_SMS_SENDER_NAME', '')
ORANGE_SMS_USE_SENDER_NAME = os.getenv('ORANGE_SMS_USE_SENDER_NAME', 'False').lower() == 'true'

# Environnement
ORANGE_SMS_USE_SANDBOX = os.getenv('ORANGE_SMS_USE_SANDBOX', 'True').lower() == 'true'

# Provider SMS (pour notifications_app)
SMS_PROVIDER = os.getenv('SMS_PROVIDER', 'orange_mali')
```

### 3. Résolution du problème cryptography

- **Downgrade cryptography** : `pip uninstall -y cryptography && rm -rf .venv/lib/python3.13/site-packages/cryptography* && pip install cryptography==43.0.3`
- **Désactivation temporaire de xhtml2pdf** dans `agent_mali_app/views.py` (fonction export PDF)

### 4. Nouvelle fonctionnalité SMS ajoutée

**Fichier créé :** `agent_chine_app/views_password_reset_sms.py`
- Vue dédiée pour réinitialiser le mot de passe et envoyer **UNIQUEMENT par SMS**
- Vérifie la configuration Orange SMS avant envoi
- Crée des logs SMS avec tracking

**Route ajoutée :** `/agent-chine/clients/<id>/reset-password-sms/` dans `agent_chine_app/urls.py`

**Template mis à jour :** `agent_chine_app/templates/agent_chine_app/client_detail.html`
- Bouton "RMP par SMS" maintenant actif
- Confirmation avec message explicite

## ✅ Vérification finale

Test effectué avec succès :

```bash
$ .venv/bin/python test_orange_sms_live.py

======================================================================
TEST SERVICE ORANGE SMS - CONFIGURATION
======================================================================

1️⃣  Variables dans settings.py:
   CLIENT_ID: 4tC3AuQK1SMN3BuWGId6... (longueur: 32)
   CLIENT_SECRET: FPPUfZkawndJea8kBvCg... (longueur: 44)
   SENDER_PHONE: +22370702150
   USE_SANDBOX: True
   SMS_PROVIDER: orange_mali

2️⃣  Service OrangeSMSService:
   is_configured(): True ✅

3️⃣  Test d'authentification OAuth2:
   ✅ Token obtenu avec succès!

======================================================================
Résultat: Le service Orange SMS est ✅ CONFIGURÉ
======================================================================
```

## 🚀 Démarrage du serveur

Pour démarrer le serveur Django avec la bonne configuration :

```bash
# Toujours utiliser le Python du venv
.venv/bin/python manage.py runserver

# OU activer le venv puis lancer
source .venv/bin/activate
python manage.py runserver
```

**⚠️ Important** : Ne pas utiliser simplement `python manage.py runserver` car cela utilise Python 2.7 du système.

## 📝 Utilisation

1. Connecte-toi en tant qu'agent Chine
2. Va sur la page de détail d'un client
3. Clique sur le bouton "**RMP par SMS**" (bouton outline-danger avec icône chat)
4. Confirme l'action
5. Le mot de passe sera réinitialisé et envoyé **uniquement par SMS** via Orange API

## 🔍 Monitoring

Les SMS envoyés sont trackés dans le modèle `SMSLog` de `notifications_app` :
- Statut : `pending`, `sent`, `failed`
- Message ID fourni par Orange
- Métadonnées (type, initiateur, etc.)

## ⚠️ Limitations temporaires

- **Export PDF désactivé** : La fonctionnalité d'export PDF des lots dans `agent_mali_app` est temporairement désactivée en raison du conflit cryptography/xhtml2pdf avec Python 3.13.

## 🎯 Prochaines étapes

1. ✅ Configuration complète Orange SMS - **FAIT**
2. ✅ Test d'authentification OAuth2 - **FAIT**
3. 🔄 Tester l'envoi SMS réel vers un numéro de test
4. 🔄 Activer l'envoi SMS dans les notifications critiques (création client, etc.)
5. 🔄 Résoudre le problème xhtml2pdf pour réactiver l'export PDF
