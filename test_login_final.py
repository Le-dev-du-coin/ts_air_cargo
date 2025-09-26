#!/usr/bin/env python
"""
Script pour tester la connexion avec override des settings
"""

import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from django.test import Client, override_settings
from django.urls import reverse
from authentication.models import CustomUser

@override_settings(ALLOWED_HOSTS=['*'])
def test_login_request():
    print('=== Test de connexion avec requête simulée ===')
    
    # Créer un client de test Django
    client = Client()
    
    # URL de connexion agent Mali
    login_url = '/authentication/login/agent_mali/'
    print(f'URL de test: {login_url}')
    
    # Récupérer d'abord la page GET pour obtenir le token CSRF
    print('\n1. Récupération du formulaire...')
    response = client.get(login_url)
    print(f'Status GET: {response.status_code}')
    
    if response.status_code != 200:
        print('Erreur lors du GET')
        return
    
    # Données de connexion pour notre agent Mali de test
    login_data = {
        'phone_number': '74683745',  # Format local
        'password': 'test123456'
    }
    
    print('\n2. Tentative de connexion...')
    print(f'Données: {login_data}')
    
    # Faire la requête POST avec les données de connexion
    response = client.post(login_url, login_data, follow=True)
    print(f'Status POST: {response.status_code}')
    
    if response.status_code == 200:
        # Analyser le contenu de la réponse
        content = response.content.decode()
        
        # Vérifier s'il y a redirection ou erreur
        if '/authentication/verify-otp/' in response.redirect_chain:
            print('✓ Redirection vers page OTP - Connexion réussie!')
            print(f'✓ Chaîne de redirection: {response.redirect_chain}')
        elif 'Invalid phone number or password' in content:
            print('❌ Erreur: "Invalid phone number or password"')
            print('   -> Vérifier les identifiants ou la normalisation')
        elif 'error' in content.lower():
            print('❌ Autres erreurs dans la réponse')
        else:
            print('? Réponse inattendue, contenu partiel:')
            print(content[:500] + '...' if len(content) > 500 else content)
            
        # Vérifier la session
        session = client.session
        print(f'\n3. Contenu de la session:')
        for key, value in session.items():
            print(f'   {key}: {value}')
    else:
        print(f'✗ Échec de connexion - Status: {response.status_code}')
    
    print('\n4. Test avec différents formats de numéros...')
    formats_test = [
        '+22374683745',  # International complet
        '22374683745',   # Sans +
        '74683745',      # Local
    ]
    
    for phone in formats_test:
        test_data = {
            'phone_number': phone,
            'password': 'test123456'
        }
        
        # Nouveau client pour chaque test pour éviter les interférences de session
        test_client = Client()
        response = test_client.post(login_url, test_data)
        
        if response.status_code == 302:  # Redirection
            print(f'✓ {phone} -> Succès (redirection vers {response.url})')
        elif response.status_code == 200:
            content = response.content.decode()
            if 'Invalid phone number or password' in content:
                print(f'✗ {phone} -> Échec (mot de passe/numéro invalide)')
            else:
                print(f'? {phone} -> Réponse 200 (peut être un formulaire avec erreurs)')
        else:
            print(f'✗ {phone} -> Échec (status {response.status_code})')

if __name__ == '__main__':
    test_login_request()