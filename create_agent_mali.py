#!/usr/bin/env python
"""
Script pour créer un agent Mali et tester l'authentification
"""

import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from authentication.models import CustomUser
from django.contrib.auth import authenticate
from authentication.forms import LoginForm

def create_and_test_agent_mali():
    print('=== Création d\'un agent Mali pour les tests ===')
    
    # Créer ou récupérer un agent Mali
    agent_mali_phone = '+22374683745'  # Numéro différent pour éviter conflits
    try:
        agent_mali = CustomUser.objects.get(telephone=agent_mali_phone)
        print(f'Agent Mali existant: {agent_mali.telephone}')
    except CustomUser.DoesNotExist:
        agent_mali = CustomUser.objects.create_user(
            telephone=agent_mali_phone,
            email='agent_mali_test@example.com',
            first_name='Agent',
            last_name='Mali Test',
            role='agent_mali'
        )
        print(f'Nouvel agent Mali créé: {agent_mali.telephone}')
    
    # Définir un mot de passe connu
    test_password = 'test123456'
    agent_mali.set_password(test_password)
    agent_mali.save()
    print(f'Mot de passe défini: {test_password}')
    
    print(f'\n=== Test d\'authentification avec l\'agent Mali ===')
    
    # Test authentification directe
    auth_user = authenticate(telephone=agent_mali_phone, password=test_password)
    if auth_user:
        print(f'✓ Authentification directe réussie: {auth_user.telephone} ({auth_user.role})')
        print(f'  - is_agent_mali: {auth_user.is_agent_mali}')
        print(f'  - is_active: {auth_user.is_active}')
    else:
        print(f'✗ Échec authentification directe')
        return
    
    print(f'\n=== Test du formulaire LoginForm avec différents formats ===')
    
    # Simuler une requête
    class MockRequest:
        def __init__(self):
            self.session = {}
    
    # Formats à tester pour l'agent Mali
    test_formats = [
        '74683745',      # Format local sans préfixe
        '+22374683745',  # Format international complet
        '22374683745',   # Format sans + mais avec indicatif
    ]
    
    for phone_input in test_formats:
        print(f'\nTest avec: {phone_input}')
        test_data = {
            'phone_number': phone_input,
            'password': test_password
        }
        
        form = LoginForm(test_data, request=MockRequest())
        if form.is_valid():
            normalized = form.cleaned_data['phone_number']
            user = form.user_cache
            print(f'  ✓ Succès: {phone_input} → {normalized}')
            print(f'  ✓ Utilisateur: {user.first_name} {user.last_name} ({user.role})')
        else:
            print(f'  ✗ Échec: {form.errors}')

if __name__ == '__main__':
    create_and_test_agent_mali()