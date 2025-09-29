# 🔧 Guide de Résolution des Problèmes de Production

## ✅ Problèmes Résolus dans cette Branche

### 1. **Clients ne s'affichent pas en production - Agent Chine** ✅

**Problème** : La liste des clients ne s'affiche pas lors de la création de colis en production.

**Cause** : Le template générait TOUTES les options HTML, même avec des milliers de clients, causant des problèmes de performance et de DOM.

**Solution** :
- **Mode Local** (≤50 clients) : Génère toutes les options HTML pour recherche instantanée
- **Mode AJAX** (>50 clients) : Utilise l'API `clients_search_api` avec pagination
- Correction du bug dans l'API : `client.adresse` au lieu de `client.adresse_complete`

**Fichiers modifiés** :
- `agent_chine_app/templates/agent_chine_app/colis_form.html`
- `agent_chine_app/views.py` (ligne 1679)

### 2. **Logo ne s'affiche pas en production - Agent Mali** ✅

**Problème** : Le logo n'apparaît pas dans la barre latérale de l'agent Mali.

**Cause** : Mauvaise référence au fichier - template utilisait `logo.jpg` mais le fichier est `logo.jpeg`.

**Solution** :
- Correction du nom de fichier dans le template
- Utilisation correcte de `{% static 'img/logo.jpeg' %}`

**Fichiers modifiés** :
- `agent_mali_app/templates/agent_mali_app/base.html`

### 3. **Prix de transport manuel corrigé** ✅

**Problème** : Le prix manuel était traité comme un prix total au lieu d'un prix par kilo.

**Solution** :
- Interface claire : "Prix par kilo (FCFA/kg)"
- Calcul automatique : prix par kilo × poids = prix total
- API mise à jour pour gérer le calcul correct
- JavaScript pour affichage en temps réel

**Fichiers modifiés** :
- `agent_chine_app/templates/agent_chine_app/colis_form.html`
- `agent_chine_app/views.py`
- `agent_chine_app/tasks.py`

### 4. **Optimisations de Performance** ✅

**Corrections apportées** :
- Suppression du filtre Django `div` inexistant
- Correction de `STATUS_CHOICES` → `TASK_STATUS_CHOICES`
- Optimisation du traitement d'images asynchrones
- Amélioration de la gestion d'erreurs

### 5. **Réception Partielle des Colis** ✅

**Statut** : ✅ **DÉJÀ FONCTIONNEL**

Le système de réception partielle est déjà bien implémenté :
- Interface avec checkboxes pour sélection individuelle
- Logique métier complète dans `recevoir_lot_view`
- Gestion des colis manquants via `ReceptionLot.colis_manquants`
- Statuts de lots correctement mis à jour

## 🚀 Instructions de Déploiement

### 1. **Vérifications Préalables**

```bash
# Vérifier que le logo existe
ls -la static/img/logo.jpeg

# Vérifier les fichiers statiques
python manage.py collectstatic --noinput
```

### 2. **Tests à Effectuer**

#### Test 1 : Sélection des Clients
- Créer un colis dans l'agent Chine
- Vérifier que la liste des clients s'affiche
- Tester la recherche (locale ou AJAX selon le nombre)

#### Test 2 : Logo Agent Mali
- Se connecter à l'agent Mali
- Vérifier que le logo apparaît dans la barre latérale

#### Test 3 : Prix Manuel
- Créer un colis avec prix manuel
- Saisir prix par kilo (ex: 10000)
- Vérifier calcul automatique du total

#### Test 4 : Réception Partielle
- Aller dans "Lots en transit" (Agent Mali)
- Réceptionner partiellement un lot
- Vérifier que les colis non sélectionnés restent en transit

### 3. **Configuration Recommandée**

#### Variables d'environnement pour la production :
```python
# settings.py pour la production
SKIP_IMAGE_PROCESSING_IN_DEV = False  # Traiter les images en prod
STATIC_URL = '/static/'
STATIC_ROOT = '/chemin/vers/static/'  # Chemin de production

# Celery pour les tâches asynchrones
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

#### Serveur web :
```nginx
# nginx.conf - Servir les fichiers statiques
location /static/ {
    alias /chemin/vers/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### 4. **Monitoring Post-Déploiement**

#### Vérifications à faire :
- [ ] Clients se chargent rapidement (< 2s)
- [ ] Logo visible dans toutes les apps
- [ ] Calcul prix manuel fonctionne
- [ ] Réception partielle OK
- [ ] Pas d'erreurs JavaScript dans la console
- [ ] Tâches Celery s'exécutent correctement

#### Métriques à surveiller :
- Temps de chargement des pages de création de colis
- Erreurs 500 dans les logs
- Performance des requêtes API clients
- Succès des tâches asynchrones

## 🐛 Dépannage

### Si les clients ne s'affichent toujours pas :
1. Vérifier les logs Django pour les erreurs API
2. Tester l'endpoint `/agent-chine/api/clients/search/` directement
3. Vérifier la console JavaScript pour les erreurs AJAX

### Si le logo ne s'affiche pas :
1. Vérifier que `python manage.py collectstatic` a été exécuté
2. Contrôler les permissions sur les fichiers statiques
3. Vérifier la configuration du serveur web (nginx/apache)

### Si le prix manuel ne fonctionne pas :
1. Vérifier que JavaScript n'a pas d'erreurs
2. Tester l'API `/agent-chine/api/calculate-price/` manuellement
3. Contrôler les données envoyées dans le formulaire

## 📝 Notes Techniques

### Architecture des Optimisations :
- **Client < 50** : Rendu côté serveur + recherche JavaScript locale
- **Client > 50** : Recherche AJAX avec pagination côté serveur
- **Prix Manuel** : Validation côté client + serveur
- **Images** : Traitement asynchrone avec optimisations multi-étapes

### Performance Attendue :
- Chargement page colis : < 2s (même avec 1000+ clients)
- Recherche client locale : < 100ms
- Recherche client AJAX : < 300ms
- Traitement image : 2-5s en arrière-plan

---

**Branche** : `fix-production-issues`
**Date** : 29 septembre 2025
**Statut** : ✅ Prêt pour le déploiement