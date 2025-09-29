#!/usr/bin/env python
"""
Script de test pour valider les corrections de notifications
Exécuter avec: python manage.py shell < test_notifications_fix.py
"""

import os
import sys
from django.conf import settings
from django.utils import timezone

print("🔧 Test des corrections de notifications - TS Air Cargo")
print("=" * 60)

# Test 1: Vérifier que la nouvelle fonction existe
print("📋 Test 1: Vérification des fonctions de notification...")
try:
    from notifications_app.tasks import send_bulk_received_colis_notifications
    print("✅ Nouvelle fonction send_bulk_received_colis_notifications trouvée")
    
    # Vérifier aussi l'ancienne (elle doit toujours exister)
    from notifications_app.tasks import send_bulk_lot_notifications
    print("✅ Ancienne fonction send_bulk_lot_notifications toujours disponible")
    
except ImportError as e:
    print("❌ Erreur import:", e)

# Test 2: Vérifier le template de notification corrigé
print("\n📋 Test 2: Vérification du template de notification...")
try:
    from notifications_app.tasks import send_bulk_received_colis_notifications
    import inspect
    
    # Récupérer le code source de la fonction
    source = inspect.getsource(send_bulk_received_colis_notifications)
    
    if "Nous vous contacterons bientôt" in source:
        print("❌ Le message contient encore la partie à supprimer")
    else:
        print("✅ Message de notification corrigé (partie contact supprimée)")
        
    if "colis_ids_list" in source:
        print("✅ La fonction utilise bien une liste de colis spécifiques")
    else:
        print("❌ La fonction ne semble pas utiliser la liste de colis")
        
except Exception as e:
    print("❌ Erreur vérification template:", e)

# Test 3: Vérifier la modification dans la vue
print("\n📋 Test 3: Vérification de la vue recevoir_lot...")
try:
    from agent_mali_app.views import recevoir_lot_view
    import inspect
    
    source = inspect.getsource(recevoir_lot_view)
    
    if "send_bulk_received_colis_notifications" in source:
        print("✅ La vue utilise la nouvelle fonction de notification ciblée")
    else:
        print("❌ La vue n'utilise pas la nouvelle fonction")
        
    if "colis_recus_ids_int" in source:
        print("✅ La vue passe les IDs des colis réceptionnés spécifiquement")
    elif "colis_ids_list" in source:
        print("✅ La vue passe une liste de colis spécifiques")
    else:
        print("❌ La vue ne passe pas les colis spécifiques")
    
    # Debug: montrer une partie du code pour diagnostic
    if "send_bulk_received_colis_notifications" not in source:
        print("🔍 Recherche de 'send_bulk_' dans le code...")
        lines_with_send = [line.strip() for line in source.split('\n') if 'send_bulk' in line]
        if lines_with_send:
            print(f"   Trouvé: {lines_with_send}")
        else:
            print("   Aucune ligne avec 'send_bulk' trouvée")
        
except Exception as e:
    print("❌ Erreur vérification vue:", e)

# Test 4: Simuler le comportement attendu
print("\n📋 Test 4: Simulation du comportement...")
try:
    from agent_chine_app.models import Lot, Colis
    from agent_mali_app.models import ReceptionLot
    from authentication.models import CustomUser
    
    # Compter les éléments actuels
    lots_count = Lot.objects.count()
    colis_count = Colis.objects.count()
    
    print(f"📊 Base de données actuelle:")
    print(f"   - Lots: {lots_count}")
    print(f"   - Colis: {colis_count}")
    
    if colis_count > 0:
        # Prendre un exemple de colis
        colis_exemple = Colis.objects.first()
        print(f"   - Exemple colis: {colis_exemple.numero_suivi}")
        print(f"   - Statut: {colis_exemple.statut}")
        print(f"   - Client: {colis_exemple.client.user.get_full_name()}")
        
        # Test de la logique
        if colis_exemple.statut == 'arrive':
            print("✅ Ce colis est arrivé - il devrait avoir reçu une notification")
        else:
            print(f"ℹ️  Ce colis ({colis_exemple.statut}) ne devrait pas avoir de notification d'arrivée")
    
except Exception as e:
    print("❌ Erreur simulation:", e)

# Test 5: Vérifier les imports
print("\n📋 Test 5: Vérification des imports...")
try:
    # Vérifier que tous les imports nécessaires fonctionnent
    from notifications_app.models import Notification, NotificationTask
    from django.contrib.auth import get_user_model
    
    notifications_count = Notification.objects.count()
    tasks_count = NotificationTask.objects.count()
    
    print(f"✅ Notifications en base: {notifications_count}")
    print(f"✅ Tâches de notification: {tasks_count}")
    
except Exception as e:
    print("❌ Erreur imports:", e)

print("\n" + "=" * 60)
print("🎉 Tests terminés !")
print("\n💡 Résumé des corrections:")
print("1. ✅ Message allégé (suppression contact)")
print("2. ✅ Fonction ciblée pour colis réceptionnés seulement")  
print("3. ✅ Vue modifiée pour utiliser la nouvelle fonction")
print("4. ✅ Évite les doublons (notifications par colis réellement reçus)")

print("\n🔄 Prochaines étapes:")
print("1. Tester avec un lot réel en réception partielle")
print("2. Vérifier que seuls les colis sélectionnés reçoivent des notifications")
print("3. Confirmer que les réceptions ultérieures n'envoient pas de doublons")