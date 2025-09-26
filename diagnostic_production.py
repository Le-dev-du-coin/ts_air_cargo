#!/usr/bin/env python
"""
Script de diagnostic pour identifier les problèmes entre local et production
"""

import os
import django
import sys
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from django.conf import settings
from authentication.models import CustomUser
from django.contrib.auth import authenticate
from authentication.forms import LoginForm
from django.core.cache import cache
import requests

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check_environment():
    """Vérifier la configuration de l'environnement"""
    print_section("CONFIGURATION ENVIRONNEMENT")
    
    print(f"DEBUG: {settings.DEBUG}")
    print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print(f"DATABASE ENGINE: {settings.DATABASES['default']['ENGINE']}")
    print(f"DATABASE NAME: {settings.DATABASES['default']['NAME']}")
    
    # Variables d'environnement critiques
    env_vars = [
        'WACHAP_SYSTEM_ACTIVE', 'WACHAP_MALI_ACTIVE', 'WACHAP_CHINE_ACTIVE',
        'WACHAP_SYSTEM_ACCESS_TOKEN', 'WACHAP_MALI_ACCESS_TOKEN', 'WACHAP_CHINE_ACCESS_TOKEN',
        'ADMIN_PHONE', 'ADMIN_EMAIL'
    ]
    
    for var in env_vars:
        value = getattr(settings, var, 'NOT_SET')
        if 'TOKEN' in var:
            # Masquer les tokens pour la sécurité
            display_value = f"{value[:8]}...{value[-4:]}" if value != 'NOT_SET' and value else 'NOT_SET'
        else:
            display_value = value
        print(f"{var}: {display_value}")

def check_database():
    """Vérifier la base de données"""
    print_section("BASE DE DONNEES")
    
    try:
        # Compter les utilisateurs
        total_users = CustomUser.objects.count()
        print(f"✅ Connexion DB réussie - {total_users} utilisateurs")
        
        # Lister les utilisateurs par rôle
        roles = CustomUser.objects.values_list('role', flat=True).distinct()
        for role in roles:
            count = CustomUser.objects.filter(role=role).count()
            print(f"   - {role}: {count}")
            
        # Vérifier un utilisateur agent Mali spécifique
        agent_mali = CustomUser.objects.filter(role='agent_mali').first()
        if agent_mali:
            print(f"✅ Agent Mali trouvé: {agent_mali.telephone}")
            # Test d'authentification
            test_auth = authenticate(telephone=agent_mali.telephone, password='test123456')
            if test_auth:
                print(f"✅ Authentification test réussie")
            else:
                print(f"❌ Authentification test échouée - vérifier le mot de passe")
        else:
            print(f"❌ Aucun agent Mali trouvé")
            
    except Exception as e:
        print(f"❌ Erreur DB: {str(e)}")

def check_wachap_connectivity():
    """Vérifier la connectivité WaChap"""
    print_section("CONNECTIVITE WACHAP")
    
    instances = [
        ('SYSTEM', settings.WACHAP_SYSTEM_ACCESS_TOKEN, settings.WACHAP_SYSTEM_INSTANCE_ID, settings.WACHAP_SYSTEM_ACTIVE),
        ('MALI', settings.WACHAP_MALI_ACCESS_TOKEN, settings.WACHAP_MALI_INSTANCE_ID, settings.WACHAP_MALI_ACTIVE),
        ('CHINE', settings.WACHAP_CHINE_ACCESS_TOKEN, settings.WACHAP_CHINE_INSTANCE_ID, settings.WACHAP_CHINE_ACTIVE),
    ]
    
    for name, token, instance_id, active in instances:
        print(f"\n🔍 Test WaChap {name}:")
        print(f"   Instance ID: {instance_id}")
        print(f"   Active: {active}")
        
        if not active:
            print(f"   ⚠️ Instance désactivée")
            continue
            
        if not token or not instance_id:
            print(f"   ❌ Token ou Instance ID manquant")
            continue
            
        try:
            # Test de connectivité WaChap API
            url = "https://wachap.wablas.com/api/v2/send-message"
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            # Test simple sans envoyer de message
            payload = {
                'instance_id': instance_id,
                'phone': '+22300000000',  # Numéro test
                'message': 'test',
                'dry_run': True  # Si supporté par l'API
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Connectivité OK")
            elif response.status_code == 401:
                print(f"   ❌ Token invalide")
            elif response.status_code == 403:
                print(f"   ❌ Instance ID invalide")
            else:
                print(f"   ⚠️ Réponse inattendue: {response.text[:100]}")
                
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout - problème réseau")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erreur réseau: {str(e)}")
        except Exception as e:
            print(f"   ❌ Erreur: {str(e)}")

def check_cache():
    """Vérifier le système de cache"""
    print_section("SYSTEME CACHE")
    
    try:
        # Test de cache basique
        test_key = f"diagnostic_test_{datetime.now().timestamp()}"
        test_value = "test_value"
        
        cache.set(test_key, test_value, 60)
        retrieved = cache.get(test_key)
        
        if retrieved == test_value:
            print("✅ Cache fonctionne correctement")
        else:
            print(f"❌ Cache défaillant - attendu: {test_value}, reçu: {retrieved}")
            
        cache.delete(test_key)
        
        # Vérifier les clés OTP existantes
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'keys'):
            # Redis cache
            otp_keys = [k for k in cache._cache.keys('*') if 'otp' in str(k)]
            print(f"Clés OTP en cache: {len(otp_keys)}")
        else:
            print("Info: Impossible de lister les clés cache")
            
    except Exception as e:
        print(f"❌ Erreur cache: {str(e)}")

def test_login_form():
    """Tester le formulaire de connexion"""
    print_section("TEST FORMULAIRE LOGIN")
    
    # Simuler une requête
    class MockRequest:
        def __init__(self):
            self.session = {}
    
    # Test avec différents formats
    test_cases = [
        ('74683745', 'test123456'),  # Format local
        ('+22374683745', 'test123456'),  # Format international
    ]
    
    for phone, password in test_cases:
        print(f"\n📝 Test: {phone} / {password}")
        
        form = LoginForm({
            'phone_number': phone,
            'password': password
        }, request=MockRequest())
        
        if form.is_valid():
            normalized = form.cleaned_data['phone_number']
            user = form.user_cache
            print(f"✅ Formulaire valide - {phone} → {normalized}")
            print(f"   Utilisateur: {user.first_name} {user.last_name} ({user.role})")
        else:
            print(f"❌ Formulaire invalide: {form.errors}")

def generate_production_checklist():
    """Générer une checklist pour la production"""
    print_section("CHECKLIST PRODUCTION")
    
    checklist = [
        "🔍 Vérifier que DEBUG=False en production",
        "🔍 Vérifier les ALLOWED_HOSTS incluent le domaine de production",
        "🔍 Vérifier que la base de données PostgreSQL est accessible",
        "🔍 Vérifier les tokens WaChap sont valides et actifs",
        "🔍 Vérifier que les instances WaChap répondent",
        "🔍 Vérifier que Redis/Cache est opérationnel",
        "🔍 Vérifier que Celery workers tournent",
        "🔍 Vérifier les logs d'application (/var/log/...)",
        "🔍 Vérifier les logs Nginx (/var/log/nginx/...)",
        "🔍 Vérifier les logs Gunicorn",
        "🔍 Tester la connectivité réseau vers WaChap depuis le serveur",
        "🔍 Vérifier que les mots de passe utilisateurs sont corrects en prod",
        "🔍 Vérifier les variables d'environnement en production",
    ]
    
    for item in checklist:
        print(item)

def main():
    print("🔧 DIAGNOSTIC TS AIR CARGO - LOCAL vs PRODUCTION")
    print(f"⏰ Exécuté le: {datetime.now()}")
    
    check_environment()
    check_database()
    check_wachap_connectivity()
    check_cache()
    test_login_form()
    generate_production_checklist()
    
    print_section("COMMANDES UTILES POUR LA PRODUCTION")
    print("# Se connecter au serveur de production")
    print("ssh user@your-server.com")
    print()
    print("# Vérifier les logs Django")
    print("tail -f /var/www/ts_air_cargo/logs/django.log")
    print()
    print("# Vérifier les services")
    print("sudo supervisorctl status ts_air_cargo:*")
    print()
    print("# Redémarrer les services")
    print("sudo supervisorctl restart ts_air_cargo:*")
    print()
    print("# Test depuis le serveur de production")
    print("cd /var/www/ts_air_cargo")
    print("source venv/bin/activate")
    print("python diagnostic_production.py")

if __name__ == '__main__':
    main()