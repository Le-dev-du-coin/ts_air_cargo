#!/usr/bin/env python
"""
Script de test rapide pour production - à exécuter sur le serveur de production
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
import requests

def quick_test():
    print("🔥 TEST RAPIDE PRODUCTION - TS AIR CARGO")
    print(f"⏰ {datetime.now()}")
    print(f"🖥️ DEBUG: {settings.DEBUG}")
    print(f"🏠 ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    
    # Test 1: Utilisateurs en base
    print(f"\n📊 UTILISATEURS:")
    users = CustomUser.objects.filter(role__in=['agent_mali', 'client', 'agent_chine'])
    for user in users:
        print(f"   {user.telephone} ({user.role}) - Active: {user.is_active}")
    
    # Test 2: Agent Mali spécifique
    print(f"\n🇲🇱 TEST AGENT MALI:")
    try:
        # Chercher un agent Mali
        agent_mali = CustomUser.objects.filter(role='agent_mali', is_active=True).first()
        if not agent_mali:
            print("❌ Aucun agent Mali actif trouvé")
            return
        
        print(f"✅ Agent Mali: {agent_mali.telephone}")
        
        # Test avec différents mots de passe courants
        test_passwords = ['test123456', 'password123', 'admin123', 'ts2024']
        
        for pwd in test_passwords:
            auth_result = authenticate(telephone=agent_mali.telephone, password=pwd)
            if auth_result:
                print(f"✅ Mot de passe trouvé: {pwd}")
                
                # Test du formulaire
                class MockRequest:
                    def __init__(self):
                        self.session = {}
                
                # Test différents formats de numéro
                phone_formats = [
                    agent_mali.telephone,  # Format stocké en DB
                    agent_mali.telephone.replace('+223', ''),  # Format local
                ]
                
                for phone_format in phone_formats:
                    form = LoginForm({
                        'phone_number': phone_format,
                        'password': pwd
                    }, request=MockRequest())
                    
                    if form.is_valid():
                        print(f"✅ Formulaire OK: {phone_format} → {form.cleaned_data['phone_number']}")
                    else:
                        print(f"❌ Formulaire KO: {phone_format} → {form.errors}")
                
                break
        else:
            print(f"❌ Aucun mot de passe testé ne fonctionne pour {agent_mali.telephone}")
            print("💡 Définir un mot de passe connu:")
            print(f"   python manage.py shell")
            print(f"   >>> from authentication.models import CustomUser")
            print(f"   >>> user = CustomUser.objects.get(telephone='{agent_mali.telephone}')")
            print(f"   >>> user.set_password('test123456')")
            print(f"   >>> user.save()")
            
    except Exception as e:
        print(f"❌ Erreur test agent Mali: {str(e)}")
    
    # Test 3: WaChap quick test
    print(f"\n📱 TEST WACHAP:")
    if settings.WACHAP_SYSTEM_ACTIVE and settings.WACHAP_SYSTEM_ACCESS_TOKEN:
        try:
            response = requests.get("https://wachap.wablas.com", timeout=5)
            print(f"✅ WaChap accessible (status: {response.status_code})")
        except Exception as e:
            print(f"❌ WaChap inaccessible: {str(e)}")
    else:
        print(f"⚠️ WaChap System désactivé ou token manquant")
    
    # Test 4: Cache
    print(f"\n💾 TEST CACHE:")
    from django.core.cache import cache
    try:
        cache.set('production_test', 'ok', 30)
        result = cache.get('production_test')
        if result == 'ok':
            print("✅ Cache fonctionne")
        else:
            print("❌ Cache défaillant")
        cache.delete('production_test')
    except Exception as e:
        print(f"❌ Erreur cache: {str(e)}")
    
    print(f"\n🎯 ACTIONS RECOMMANDÉES:")
    print("1. Si aucun utilisateur n'a de mot de passe valide → Définir des mots de passe connus")
    print("2. Si WaChap inaccessible → Vérifier connectivité réseau depuis le serveur")
    print("3. Si cache défaillant → Vérifier Redis: redis-cli ping")
    print("4. Tester la connexion web: https://ts-aircargo.com/authentication/login/agent_mali/")

if __name__ == '__main__':
    quick_test()