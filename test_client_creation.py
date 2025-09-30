#!/usr/bin/env python
"""
Script de test pour diagnostiquer le problème de création de client
Exécuter avec: python manage.py shell < test_client_creation.py
"""

from agent_chine_app.client_management import ClientAccountManager

print("🔧 Test de création de client")
print("=" * 50)

# Test 1: Test avec données valides
print("📋 Test 1: Création avec données valides...")
try:
    result = ClientAccountManager.get_or_create_client_with_password(
        telephone="+22376123456",
        first_name="Test",
        last_name="Client",
        email="test@example.com",
        password="password123",
        notify=False
    )
    print(f"✅ Succès: {result}")
    
    # Nettoyer le test
    if result['created']:
        result['client'].delete()
        print("🗑️ Client de test supprimé")
        
except Exception as e:
    print(f"❌ Erreur: {e}")

# Test 2: Test avec téléphone vide
print("\n📋 Test 2: Création avec téléphone vide...")
try:
    result = ClientAccountManager.get_or_create_client_with_password(
        telephone="",
        first_name="Test",
        last_name="Client",
        email="test@example.com",
        password="password123",
        notify=False
    )
    print(f"❌ Ne devrait pas réussir: {result}")
except Exception as e:
    print(f"✅ Erreur attendue: {e}")

# Test 3: Test avec téléphone None
print("\n📋 Test 3: Création avec téléphone None...")
try:
    result = ClientAccountManager.get_or_create_client_with_password(
        telephone=None,
        first_name="Test",
        last_name="Client",
        email="test@example.com",
        password="password123",
        notify=False
    )
    print(f"❌ Ne devrait pas réussir: {result}")
except Exception as e:
    print(f"✅ Erreur attendue: {e}")

# Test 4: Test de nettoyage du numéro
print("\n📋 Test 4: Test de nettoyage du numéro...")
try:
    from agent_chine_app.client_management import ClientAccountManager
    
    # Tests de formats différents
    test_phones = [
        "99281899",
        "0099281899", 
        "22399281899",
        "+22399281899",
        "  +223 99 28 18 99  ",
        "(223) 99-28-18-99",
    ]
    
    for phone in test_phones:
        try:
            cleaned = ClientAccountManager._clean_phone_number(phone)
            print(f"   '{phone}' → '{cleaned}'")
        except Exception as e:
            print(f"   '{phone}' → ERROR: {e}")
            
except Exception as e:
    print(f"❌ Erreur test nettoyage: {e}")

print("\n" + "=" * 50)
print("🎉 Tests terminés !")
print("\n💡 Solutions possibles:")
print("1. Vérifier que le champ téléphone est bien rempli dans le formulaire")
print("2. Vérifier la validation JavaScript côté client")
print("3. Ajouter des logs pour voir les données POST reçues")
print("4. Vérifier le nom du champ dans le template HTML")