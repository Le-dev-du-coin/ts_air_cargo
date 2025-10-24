# Configuration Orange SMS API

## Vue d'ensemble

Ce système utilise l'API Orange SMS (OAuth2) pour l'envoi de SMS transactionnels (réinitialisation de mot de passe, notifications critiques).

**Documentation officielle** : https://developer.orange.com/apis/sms/

---

## Étapes de Configuration

### 1. Créer un compte développeur Orange

1. Allez sur https://developer.orange.com/
2. Créez un compte développeur
3. Validez votre email

### 2. Créer une application

1. Connectez-vous à votre compte développeur
2. Allez dans "My apps"
3. Cliquez sur "Add a new app"
4. Remplissez les informations :
   - **Name** : TS Air Cargo SMS
   - **Description** : Application d'envoi de SMS pour TS Air Cargo
5. Sélectionnez l'API **"SMS"**
6. Choisissez le pays : **Mali** (ou votre pays)
7. Validez

### 3. Récupérer les credentials

Après création de l'app, vous obtiendrez :
- **Client ID** (App Key)
- **Client Secret** (App Secret)

⚠️ **Important** : Gardez ces credentials sécurisés !

---

## Configuration dans votre projet

### Ajouter dans `.env`

```bash
# Orange SMS API Configuration
ORANGE_SMS_CLIENT_ID=votre_client_id_ici
ORANGE_SMS_CLIENT_SECRET=votre_client_secret_ici

# Sender (Numéro de téléphone REQUIS pour commencer)
ORANGE_SMS_SENDER_PHONE=+223XXXXXXXX

# Sender Name (nom personnalisé, après validation Orange)
ORANGE_SMS_SENDER_NAME=TSAIRCARGO

# Activer l'utilisation du Sender Name (False jusqu'à validation Orange)
ORANGE_SMS_USE_SENDER_NAME=False

# Environnement (True pour sandbox/test, False pour production)
ORANGE_SMS_USE_SANDBOX=True

# Provider SMS par défaut
SMS_PROVIDER=orange_mali
```

### Exemple de configuration complète

```bash
# === SMS Configuration ===
SMS_PROVIDER=orange_mali

# Orange SMS API
ORANGE_SMS_CLIENT_ID=AbCdEfGh1234567890
ORANGE_SMS_CLIENT_SECRET=1a2b3c4d5e6f7g8h9i0j
ORANGE_SMS_SENDER_PHONE=+22373451676
ORANGE_SMS_SENDER_NAME=TSAIRCARGO
ORANGE_SMS_USE_SENDER_NAME=False
ORANGE_SMS_USE_SANDBOX=True
```

---

## Authentification Orange API

### Processus OAuth2

L'API Orange SMS utilise OAuth2 avec les étapes suivantes :

1. **Obtention du token** :
   ```
   POST https://api.orange.com/oauth/v3/token
   Authorization: Basic {base64(client_id:client_secret)}
   Content-Type: application/x-www-form-urlencoded
   
   grant_type=client_credentials
   ```

2. **Envoi SMS** :
   ```
   POST https://api.orange.com/smsmessaging/v1/outbound/{sender}/requests
   Authorization: Bearer {access_token}
   Content-Type: application/json
   ```

### Cache des tokens

Le système cache automatiquement les tokens pour éviter les appels répétés :
- **Durée** : 1 heure (3600s)
- **Sécurité** : Cache expire 5 minutes avant l'expiration réelle
- **Renouvellement** : Automatique à l'expiration

---

## Test de la configuration

### Via Django shell

```bash
python manage.py shell
```

```python
from notifications_app.orange_sms_service import test_orange_sms_configuration

# Tester la configuration
test_orange_sms_configuration()

# Si configuré, tester l'authentification
from notifications_app.orange_sms_service import orange_sms_service
token = orange_sms_service.get_access_token()
print(f"Token obtenu: {token[:20]}..." if token else "Échec")
```

### Via script de test

```bash
python -c "from notifications_app.orange_sms_service import test_orange_sms_configuration; test_orange_sms_configuration()"
```

---

## Sender Name (Nom d'expéditeur personnalisé)

### Pourquoi utiliser un Sender Name ?

Au lieu de  `+223XXXXXXXX`, vos SMS afficheront **"TSAIRCARGO"** ou **"TS Air Cargo"**

### Comment l'obtenir ?

1. **Contacter Orange Business** :
   - Email : business@orange.ml (Mali)
   - Téléphone : Contacter votre agence Orange locale
   
2. **Documents requis** :
   - Registre de commerce
   - Lettre de demande de Sender Name
   - Copie de la pièce d'identité du responsable
   
3. **Délai** : Généralement 1-2 semaines

4. **Coût** : Variable selon le pays (gratuit au Mali en général)

### Configuration une fois obtenu

```bash
# Dans .env
ORANGE_SMS_SENDER_NAME=TSAIRCARGO
ORANGE_SMS_USE_SENDER_NAME=True  # <-- Activer ici après validation
```

**Important** : Le système utilise le Sender Name UNIQUEMENT si :
1. `ORANGE_SMS_SENDER_NAME` est défini
2. `ORANGE_SMS_USE_SENDER_NAME=True`

Sinon, il utilise `ORANGE_SMS_SENDER_PHONE` par défaut.

---

## Tarification

### Mali (Orange Mali)

- **Prix par SMS** : ~25-30 FCFA (varie selon contrat)
- **SMS entrant (DLR)** : Gratuit
- **Crédit minimum** : Selon contrat (généralement 10,000 FCFA)

### Sandbox (Test)

- **Gratuit** : Les SMS en mode sandbox sont gratuits
- **Limitation** : 10-20 SMS/jour
- **Numéros de test** : Fournis par Orange

---

## Fonctionnalités Supportées

### ✅ Implémenté

- OAuth2 authentication automatique (Basic + Bearer)
- Cache des tokens (1h - 5min sécurité)
- Envoi de SMS transactionnel
- Tracking des SMS (modèle `SMSLog`)
- Gestion d'erreurs complète
- Support Sandbox et Production
- Format automatique des numéros (Mali)
- Sender Name avec contrôle booléen (USE_SENDER_NAME)

### 🕒 À venir

- Delivery Reports (webhooks)
- SMS programmés
- Messages bulk
- Statistiques détaillées

---

## Utilisation dans le Code

### Envoi simple

```python
from notifications_app.orange_sms_service import send_orange_sms

# Envoyer un SMS
success, message_id = send_orange_sms(
    phone='+22312345678',
    message='Votre code est: 123456'
)

if success:
    print(f"SMS envoyé, ID: {message_id}")
else:
    print(f"Échec: {message_id}")
```

### Envoi avec tracking

```python
from notifications_app.orange_sms_service import orange_sms_service
from notifications_app.models import SMSLog

# Créer le log
sms_log = SMSLog.objects.create(
    user=user,
    destinataire_telephone=phone,
    message=message,
    provider='orange',
    statut='pending'
)

# Envoyer
success, message_id, response_data = orange_sms_service.send_sms(phone, message)

# Mettre à jour le log
if success:
    sms_log.mark_as_sent(message_id)
else:
    sms_log.mark_as_failed(message_id)
```

---

## Débogage

### Logs

Les logs SMS sont dans :
```bash
tail -f logs/django.log | grep -i "sms\|orange"
```

### Vérifier le statut

```python
from notifications_app.models import SMSLog

# Derniers SMS
recent_sms = SMSLog.objects.all()[:10]
for sms in recent_sms:
    print(f"{sms.destinataire_telephone} - {sms.get_statut_display()} - {sms.created_at}")
```

### Problèmes courants

1. **"Configuration manquante"** :
   - Vérifiez `ORANGE_SMS_CLIENT_ID` et `ORANGE_SMS_CLIENT_SECRET` dans `.env`

2. **"Impossible d'obtenir le token"** :
   - Vérifiez que les credentials sont corrects
   - Vérifiez votre connexion internet
   - Contactez Orange si le problème persiste

3. **"Sender non configuré"** :
   - Normal si vous n'avez pas encore le Sender Name
   - Configurez `ORANGE_SMS_SENDER_PHONE` en attendant

4. **SMS non reçu** :
   - Vérifiez que le numéro est au format international (+223...)
   - Vérifiez vos crédits Orange
   - En sandbox, vérifiez que le numéro est dans la whitelist

---

## Sécurité

### Bonnes pratiques

1. **Ne jamais commiter les credentials** :
   ```bash
   # .gitignore doit contenir
   .env
   .env.local
   ```

2. **Rotation des secrets** :
   - Changez vos credentials tous les 6 mois
   - Après tout départ d'employé ayant eu accès

3. **Limitation de débit** :
   - Le système a un cache token (évite les appels répétés)
   - Implémentez un rate limiting côté applicatif si besoin

---

## Support

### Orange Support

- **Mali** : +223 44 93 88 88
- **Email** : support.api@orange.com
- **Documentation** : https://developer.orange.com/apis/sms/

### Support TS Air Cargo

- Vérifier la documentation : `ORANGE_SMS_CONFIG.md`
- Logs système : `logs/django.log`
- Tests : `python manage.py shell`

---

## Checklist Déploiement

- [ ] Compte développeur Orange créé
- [ ] Application SMS créée
- [ ] Client ID et Secret récupérés
- [ ] Variables `.env` configurées
- [ ] Test d'authentification réussi
- [ ] SMS de test envoyé et reçu
- [ ] Crédits SMS rechargés (production)
- [ ] Monitoring mis en place
- [ ] Documentation équipe mise à jour

---

**Version** : 1.0  
**Dernière mise à jour** : 2025-10-24  
**Statut** : ✅ Système prêt, en attente de configuration Orange SMS
