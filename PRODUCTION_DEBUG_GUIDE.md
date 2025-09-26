# 🚨 Guide de Débogage Production - TS Air Cargo

## Problème Identifié
✅ **L'authentification fonctionne en local** mais **échoue en production** avec "Invalid phone number or password"

## 🔍 Diagnostic Étape par Étape

### 1. Connexion au Serveur de Production
```bash
# Se connecter au serveur
ssh user@your-production-server.com

# Aller dans le répertoire du projet
cd /var/www/ts_air_cargo

# Activer l'environnement virtuel
source venv/bin/activate
```

### 2. Vérifier les Services
```bash
# Status des services
sudo supervisorctl status ts_air_cargo:*

# Si les services sont down
sudo supervisorctl restart ts_air_cargo:*

# Vérifier les logs système
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server
```

### 3. Exécuter le Diagnostic
```bash
# Copier le script de diagnostic sur le serveur
python diagnostic_production.py

# Examiner les résultats pour identifier :
# ❌ Variables d'environnement manquantes
# ❌ Problèmes de base de données
# ❌ Connectivité WaChap
# ❌ Cache/Redis
```

### 4. Points de Vérification Critiques

#### A. Variables d'Environnement
```bash
# Vérifier le fichier .env en production
cat .env

# Comparer avec .env.production (modèle)
# Points critiques :
# - DEBUG=False
# - ALLOWED_HOSTS incluent le domaine
# - Tokens WaChap différents de dev
# - Base de données PostgreSQL
# - CELERY_TASK_ALWAYS_EAGER=False
```

#### B. Base de Données
```bash
# Test connexion PostgreSQL
sudo -u postgres psql ts_air_cargo -c "SELECT COUNT(*) FROM authentication_customuser;"

# Vérifier les utilisateurs
python manage.py shell
>>> from authentication.models import CustomUser
>>> CustomUser.objects.all().values('telephone', 'role', 'is_active')
>>> # Vérifier les mots de passe
>>> from django.contrib.auth import authenticate
>>> authenticate(telephone='+22374683745', password='le-vrai-mot-de-passe')
```

#### C. Logs d'Application
```bash
# Logs Django
tail -f logs/django.log
tail -f logs/django_error.log

# Logs Gunicorn
sudo tail -f /var/log/supervisor/ts_air_cargo_gunicorn.log

# Logs Nginx
sudo tail -f /var/log/nginx/ts_aircargo_access.log
sudo tail -f /var/log/nginx/ts_aircargo_error.log
```

### 5. Problèmes Courants et Solutions

#### 🔥 Problème 1: Mots de passe différents entre Local/Prod
```bash
# En production, définir les mêmes mots de passe qu'en local
python manage.py shell
>>> from authentication.models import CustomUser
>>> user = CustomUser.objects.get(telephone='+22374683745')
>>> user.set_password('test123456')  # ou le vrai mot de passe
>>> user.save()
```

#### 🔥 Problème 2: Tokens WaChap invalides en production
```bash
# Tester les tokens WaChap depuis le serveur de production
curl -X POST "https://wachap.wablas.com/api/v2/send-message" \
  -H "Authorization: your-production-token" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "your-production-instance-id",
    "phone": "+22373451676",
    "message": "Test connectivity"
  }'
```

#### 🔥 Problème 3: Cache/Redis non fonctionnel
```bash
# Vérifier Redis
redis-cli ping

# Test cache Django
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value', 30)
>>> cache.get('test')
```

#### 🔥 Problème 4: Celery workers non actifs
```bash
# Status Celery
sudo supervisorctl status ts_air_cargo:ts_air_cargo_celery

# Logs Celery
sudo tail -f /var/log/supervisor/ts_air_cargo_celery.log

# Relancer si nécessaire
sudo supervisorctl restart ts_air_cargo:ts_air_cargo_celery
```

### 6. Test de Connexion en Production

```bash
# Test direct avec curl
curl -X POST "https://ts-aircargo.com/authentication/login/agent_mali/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -c cookies.jar \
  -b cookies.jar \
  -d "phone_number=74683745" \
  -d "password=test123456" \
  --location-trusted

# Analyser la réponse :
# - 302 = Succès (redirection vers OTP)
# - 200 avec erreur = Problème identifié
# - 500 = Erreur serveur (vérifier logs)
```

### 7. Actions de Dépannage Rapide

#### Quick Fix 1: Redémarrage Complet
```bash
sudo supervisorctl restart ts_air_cargo:*
sudo systemctl restart nginx
sudo systemctl restart redis-server
```

#### Quick Fix 2: Forcer la Mise à Jour
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

#### Quick Fix 3: Vider le Cache
```bash
redis-cli FLUSHALL
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

## 🎯 Actions Prioritaires à Exécuter

1. **IMMÉDIAT**: Vérifier que les utilisateurs existent en production avec les bons mots de passe
2. **URGENT**: Vérifier les variables d'environnement (surtout les tokens WaChap)
3. **IMPORTANT**: Vérifier que les services (Redis, Celery, PostgreSQL) sont actifs
4. **SUIVI**: Monitorer les logs pendant un test de connexion

## 📞 Debug en Temps Réel

Pour déboguer en temps réel, ouvrir 3 terminaux sur le serveur de production :

**Terminal 1 - Logs Django :**
```bash
tail -f /var/www/ts_air_cargo/logs/django.log
```

**Terminal 2 - Logs Nginx :**
```bash
sudo tail -f /var/log/nginx/ts_aircargo_error.log
```

**Terminal 3 - Test :**
```bash
# Tester la connexion depuis le navigateur ou curl
# Observer les logs dans les 2 autres terminaux
```

## 🔧 Script de Réparation Automatique

Si nécessaire, créer un script de réparation :

```bash
#!/bin/bash
echo "🔧 Réparation automatique TS Air Cargo"

# Redémarrer tous les services
sudo supervisorctl restart ts_air_cargo:*

# Vider le cache
redis-cli FLUSHALL

# Migrations et static
cd /var/www/ts_air_cargo
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput

# Test de santé
if curl -f -s https://ts-aircargo.com/ > /dev/null; then
    echo "✅ Application opérationnelle"
else
    echo "❌ Problème persistant"
fi
```

Le problème le plus probable est une **différence de mots de passe** entre local et production, ou des **tokens WaChap invalides** en production.