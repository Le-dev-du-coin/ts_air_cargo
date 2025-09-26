#!/usr/bin/env python
"""
Script de test pour l'authentification
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

def test_auth():
    print('=== Listing des utilisateurs existants ===')
    users = CustomUser.objects.all()
    for user in users:
        print(f'{user.telephone} - {user.role} - {user.first_name} {user.last_name}')
    
    print('\n=== Test du formulaire LoginForm ===')
    
    # Simuler une requête POST
    class MockRequest:
        def __init__(self):
            self.session = {}
    
    # Tester avec un numéro malien
    test_data = {
        'phone_number': '73451676',  # Format local
        'password': 'test123456'
    }
    form = LoginForm(test_data, request=MockRequest())
    print(f'Form data: {test_data}')
    print(f'Form valid: {form.is_valid()}')
    
    if form.errors:
        print(f'Form errors: {form.errors}')
    
    if form.is_valid():
        normalized_phone = form.cleaned_data['phone_number']
        print(f'Numéro normalisé: {normalized_phone}')
        
        # Test d'authentification directe
        user = authenticate(telephone=normalized_phone, password='test123456')
        print(f'Utilisateur authentifié: {user}')
        if user:
            print(f'Utilisateur trouvé: {user.telephone} - {user.role}')
        else:
            print('Échec de l\'authentification')
    else:
        print('Formulaire invalide')
    
    print('\n=== Test avec différents formats de numéros ===')
    test_phones = [
        '73451676',       # Local malien
        '+22373451676',   # International malien 
        '22373451676',    # Sans +
        '67123456',       # Autre format local
        '+22367123456'    # Autre international
    ]
    
    for phone in test_phones:
        test_data = {'phone_number': phone, 'password': 'test123456'}
        form = LoginForm(test_data, request=MockRequest())
        if form.is_valid():
            normalized = form.cleaned_data['phone_number']
            print(f'{phone} -> {normalized}')
        else:
            print(f'{phone} -> INVALIDE: {form.errors}')

if __name__ == '__main__':
    test_auth()