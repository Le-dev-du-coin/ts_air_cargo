# Configuration SMS pour TS Air Cargo

## Ajouter dans votre fichier `settings.py` ou `settings_local.py`

### Option 1 : Twilio (Recommandé - International)

```python
# Configuration SMS via Twilio
SMS_PROVIDER = 'twilio'

# Identifiants Twilio (à obtenir sur https://www.twilio.com/console)
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='')  # Format: +1234567890
```

**Installation requise** :
```bash
pip install twilio
```

**Avantages** :
- Très fiable
- Support international
- Documentation excellente
- Essai gratuit disponible

**Prix** : ~0.0075 USD par SMS (varie selon destination)

---

### Option 2 : AWS SNS (Si infrastructure AWS existante)

```python
# Configuration SMS via AWS SNS
SMS_PROVIDER = 'aws_sns'

# Identifiants AWS (IAM user avec permissions SNS:Publish)
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
AWS_SNS_REGION = env('AWS_SNS_REGION', default='us-east-1')
```

**Installation requise** :
```bash
pip install boto3
```

**Avantages** :
- Intégration native si déjà sur AWS
- Tarification compétitive
- Scalable

**Prix** : ~0.00645 USD par SMS (varie selon destination)

---

### Option 3 : Orange Mali API (Local Mali)

```python
# Configuration SMS via Orange Mali
SMS_PROVIDER = 'orange_mali'

# Identifiants Orange Mali API
ORANGE_MALI_API_KEY = env('ORANGE_MALI_API_KEY', default='')
ORANGE_MALI_SENDER_ID = env('ORANGE_MALI_SENDER_ID', default='TS AIR CARGO')
ORANGE_MALI_API_URL = env('ORANGE_MALI_API_URL', default='https://api.orange.com/smsmessaging/v1/outbound')
```

**Installation requise** :
```bash
pip install requests  # Normalement déjà installé
```

**Avantages** :
- Provider local (Mali)
- Peut être moins cher localement
- Bonne délivrabilité au Mali

**Prix** : À vérifier avec Orange Mali

---

## Configuration via fichier .env (Recommandé)

Ajoutez dans votre fichier `.env` :

### Pour Twilio :
```bash
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

### Pour AWS SNS :
```bash
SMS_PROVIDER=aws_sns
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_SNS_REGION=us-east-1
```

### Pour Orange Mali :
```bash
SMS_PROVIDER=orange_mali
ORANGE_MALI_API_KEY=your_api_key_here
ORANGE_MALI_SENDER_ID=TS AIR CARGO
```

---

## Test de la configuration

Après configuration, testez avec :

```python
python manage.py shell

from notifications_app.sms_service import test_sms_configuration
test_sms_configuration()
```

Ou pour envoyer un SMS de test :

```python
from notifications_app.sms_service import SMSService

# Remplacez par votre numéro de test
success, message_id = SMSService.send_sms('+22312345678', 'Test SMS TS Air Cargo')
print(f"Succès: {success}, ID: {message_id}")
```

---

## Recommandation pour démarrer

**Pour démarrer rapidement** : Utilisez **Twilio**

1. Créez un compte sur https://www.twilio.com/try-twilio
2. Obtenez $15 de crédit gratuit pour tester
3. Récupérez vos identifiants dans le Console
4. Ajoutez-les dans votre `.env`
5. Installez `pip install twilio`
6. Testez !

**Après validation** : Évaluez **Orange Mali** pour réduire les coûts sur le marché local.

---

## Comportement si non configuré

Si aucun provider SMS n'est configuré :
- Le système fonctionnera quand même
- Les SMS seront "simulés" (logged uniquement)
- Les notifications WhatsApp continueront de fonctionner
- L'agent verra un message d'avertissement avec le mot de passe

---

## Intégration dans le code

Le système est déjà intégré :

1. **Réinitialisation mot de passe** : Envoie WhatsApp + SMS automatiquement
2. **Création compte** : Peut être configuré pour envoyer WhatsApp + SMS
3. **Notifications critiques** : Utilisent `send_critical_notification()`

Pas de modification de code nécessaire, juste la configuration !

---

## Support et dépannage

### Erreur : "Module twilio non installé"
```bash
pip install twilio
```

### Erreur : "Configuration Twilio incomplète"
Vérifiez que les 3 variables sont définies :
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_PHONE_NUMBER

### Erreur : "Failed to send SMS"
- Vérifiez le format du numéro : +223XXXXXXXX (international)
- Vérifiez vos crédits Twilio
- Vérifiez les logs Django pour plus de détails

### Les SMS ne sont pas reçus
- Vérifiez que le numéro est au format international (+223...)
- Pour Twilio trial : vérifiez que le numéro est vérifié dans votre compte
- Vérifiez les logs de votre provider (Twilio Console, AWS CloudWatch, etc.)

---

Bon déploiement ! 🚀
