#!/usr/bin/env python
"""
Script de test rapide pour valider les corrections de production
Exécuter avec: python manage.py shell < test_production_fixes.py
"""

import os
import sys
from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth import get_user_model

print("🔧 Test des corrections de production - TS Air Cargo")
print("=" * 60)

# Test 1: Vérification du logo
print("📋 Test 1: Vérification du fichier logo...")
logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.jpeg')
if os.path.exists(logo_path):
    print("✅ Logo trouvé:", logo_path)
    print(f"   Taille: {os.path.getsize(logo_path)} bytes")
else:
    print("❌ Logo non trouvé:", logo_path)

# Test 2: API clients search
print("\n📋 Test 2: API de recherche clients...")
try:
    from agent_chine_app.views import clients_search_api
    from agent_chine_app.models import Client
    
    client_count = Client.objects.count()
    print(f"✅ Nombre de clients en base: {client_count}")
    
    if client_count > 50:
        print("   Mode AJAX sera utilisé (>50 clients)")
    else:
        print("   Mode local sera utilisé (≤50 clients)")
        
except ImportError as e:
    print("❌ Erreur import:", e)

# Test 3: Vérification du prix manuel
print("\n📋 Test 3: Logique prix manuel...")
try:
    from agent_chine_app.views import calculate_manual_price_total
    
    # Test du calcul
    prix_par_kilo = "10000"  # 10 000 FCFA/kg
    poids = "2.5"           # 2.5 kg
    prix_total = calculate_manual_price_total(prix_par_kilo, poids)
    
    if prix_total == 25000.0:
        print("✅ Calcul prix manuel correct:")
        print(f"   {prix_par_kilo} FCFA/kg × {poids} kg = {prix_total} FCFA")
    else:
        print("❌ Erreur calcul prix:", prix_total)
        
except Exception as e:
    print("❌ Erreur prix manuel:", e)

# Test 4: Modèles de réception
print("\n📋 Test 4: Modèles de réception partielle...")
try:
    from agent_mali_app.models import ReceptionLot
    from agent_chine_app.models import Lot
    
    lots_en_transit = Lot.objects.filter(statut__in=['expedie', 'en_transit']).count()
    receptions = ReceptionLot.objects.count()
    
    print(f"✅ Lots en transit: {lots_en_transit}")
    print(f"✅ Réceptions enregistrées: {receptions}")
    
except Exception as e:
    print("❌ Erreur modèles:", e)

# Test 5: Templates critiques
print("\n📋 Test 5: Templates critiques...")
templates_to_check = [
    'agent_chine_app/templates/agent_chine_app/colis_form.html',
    'agent_mali_app/templates/agent_mali_app/base.html',
    'agent_mali_app/templates/agent_mali_app/recevoir_lot.html'
]

for template_path in templates_to_check:
    full_path = os.path.join(settings.BASE_DIR, template_path)
    if os.path.exists(full_path):
        print(f"✅ Template OK: {template_path}")
    else:
        print(f"❌ Template manquant: {template_path}")

# Test 6: Configuration Celery
print("\n📋 Test 6: Configuration Celery...")
try:
    if hasattr(settings, 'CELERY_BROKER_URL'):
        print("✅ CELERY_BROKER_URL configuré")
    else:
        print("⚠️  CELERY_BROKER_URL non configuré (normal en dev)")
        
    from agent_chine_app.tasks import create_colis_async
    print("✅ Tâches Celery importables")
    
except Exception as e:
    print("❌ Erreur Celery:", e)

print("\n" + "=" * 60)
print("🎉 Tests terminés !")
print("\n💡 Instructions de déploiement:")
print("1. Merger la branche 'fix-production-issues'")
print("2. Exécuter 'python manage.py collectstatic'")
print("3. Redémarrer les services (Django + Celery)")
print("4. Tester les fonctionnalités en production")
print("\n📖 Voir PRODUCTION_FIXES.md pour les détails")