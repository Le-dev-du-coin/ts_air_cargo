# Test du Bouton Retry Notifications

## Description
Bouton "Notifier clients" ajouté dans la page de détail des lots (`lot_detail.html`) pour renvoyer les notifications échouées ou en attente.

## Fichiers modifiés
1. `agent_chine_app/views.py` - Ajout de l'API `lot_notifications_count_api`
2. `agent_chine_app/urls.py` - Ajout de la route API
3. `agent_chine_app/templates/agent_chine_app/lot_detail.html` - UI + JavaScript

## Fonctionnalités implémentées

### 1. API pour compter les notifications
- **Endpoint**: `GET /agent-chine/api/lots/<lot_id>/notifications/count/`
- **Réponse**: `{"success": true, "count": X}`
- **Filtrage**: Compte uniquement les notifications avec `statut` in `['echec', 'en_attente']`

### 2. Bouton UI dans lot_detail
- Visible uniquement pour les lots avec `statut='ouvert'`
- Affiche un badge avec le nombre de notifications en échec/attente
- Badge orange si count > 0, vert si count = 0
- Texte: "Notifier clients"
- Icône: `bi-send`

### 3. Comportement JavaScript
- **Au chargement**: Appel automatique de l'API pour charger le compteur
- **Au clic**: 
  1. Demande de confirmation
  2. Affichage d'un spinner pendant l'envoi
  3. Appel POST à `/agent-chine/lots/<lot_id>/retry-notifications/`
  4. Affichage d'un toast Bootstrap avec le résultat
  5. Rechargement du compteur

## Comment tester

### Prérequis
1. Serveur Django en cours d'exécution
2. Au moins un lot avec `statut='ouvert'`
3. Des notifications en échec ou en attente pour ce lot

### Étapes de test

#### Test 1: Affichage du badge
1. Accéder à la page de détail d'un lot ouvert
2. Vérifier que le bouton "Notifier clients" est visible
3. Vérifier que le badge affiche le nombre correct de notifications en échec/attente

**Requête SQL pour vérifier manuellement**:
```sql
SELECT COUNT(*) 
FROM notifications_app_notification 
WHERE lot_reference_id = <LOT_ID> 
  AND statut IN ('echec', 'en_attente');
```

#### Test 2: Retry des notifications
1. Cliquer sur le bouton "Notifier clients"
2. Confirmer l'action dans la modale
3. Vérifier que:
   - Un spinner s'affiche pendant l'envoi
   - Un toast de succès/erreur apparaît
   - Le badge se met à jour avec le nouveau compteur
   - Les notifications ont été renvoyées (vérifier dans la table `notifications_app_notification`)

#### Test 3: Cas limites
1. **Lot sans notifications**: Badge devrait afficher "0" et être vert
2. **Lot fermé**: Le bouton ne devrait PAS être visible
3. **Lot expédié**: Le bouton ne devrait PAS être visible
4. **Erreur API**: Toast d'erreur devrait s'afficher

### Vérification en base de données

Après avoir cliqué sur "Retry":
```sql
-- Vérifier que les notifications ont été remises à zéro
SELECT id, statut, nombre_tentatives, prochaine_tentative
FROM notifications_app_notification
WHERE lot_reference_id = <LOT_ID>
ORDER BY id;
```

### Endpoints à tester manuellement

#### 1. API Count
```bash
curl -X GET http://localhost:8000/agent-chine/api/lots/1/notifications/count/ \
  -H "Cookie: sessionid=<SESSION_ID>"
```

#### 2. API Retry
```bash
curl -X POST http://localhost:8000/agent-chine/lots/1/retry-notifications/ \
  -H "Cookie: sessionid=<SESSION_ID>" \
  -H "X-CSRFToken: <CSRF_TOKEN>"
```

## Tests automatisés (TODO)

À implémenter dans `agent_chine_app/tests.py`:
- Test unitaire de `lot_notifications_count_api`
- Test unitaire de `retry_lot_notifications`
- Test d'intégration du flow complet
- Test des permissions (agent_chine_required)

## Comportement attendu

### Scénario nominal
1. Agent Chine ouvre la page d'un lot ouvert
2. Le badge affiche "3" (3 notifications en échec)
3. Agent clique sur "Notifier clients"
4. Confirmation: "Êtes-vous sûr de vouloir renvoyer toutes les notifications en échec pour ce lot ?"
5. Pendant l'envoi: "Envoi en cours..." avec spinner
6. Succès: Toast vert "✅ 2/3 notification(s) renvoyée(s) avec succès pour le lot LOT-001. 1 échec(s)."
7. Le badge se met à jour avec "1"

### Gestion des erreurs
- **Lot non ouvert**: Réponse HTTP 400
- **Erreur serveur**: Toast rouge avec message d'erreur
- **API déconnectée**: Les notifications échouent mais sont enregistrées en base

## Logs à vérifier
- `NotificationService.retry_notifications_for_lot()` log chaque tentative
- Les échecs sont enregistrés avec le message d'erreur
- Le nombre de tentatives est incrémenté

## Améliorations futures (cf. plan)
1. Dashboard centralisé de monitoring
2. Retry automatique avec backoff exponentiel
3. Notifications groupées
4. Statistiques de taux de succès
5. Alertes pour les échecs répétés
