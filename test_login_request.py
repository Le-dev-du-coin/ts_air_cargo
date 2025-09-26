#!/usr/bin/env python
"""
Script pour tester la connexion avec une requête HTTP simulée
"""

import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from authentication.models import CustomUser

def test_login_request():
    print('=== Test de connexion avec requête simulée ===')
    
    # Créer un client de test Django
    client = Client()
    
    # URL de connexion agent Mali
    login_url = reverse('authentication:role_based_login', kwargs={'role': 'agent_mali'})
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
    response = client.post(login_url, login_data)
    print(f'Status POST: {response.status_code}')
    
    if response.status_code == 302:  # Redirection = succès
        print(f'✓ Redirection vers: {response.url}')
        print('✓ Connexion réussie!')
        
        # Vérifier la session
        session = client.session
        if 'otp_telephone' in session:
            print(f'✓ OTP en attente pour: {session["otp_telephone"]}')
        if '_auth_user_id' in session:
            user_id = session['_auth_user_id']
            user = CustomUser.objects.get(id=user_id)
            print(f'✓ Utilisateur connecté: {user.telephone} ({user.role})')
    else:
        print(f'✗ Échec de connexion')
        print(f'Contenu de la réponse: {response.content.decode()[:1000]}...')
        
        # Analyser les erreurs dans le contenu HTML
        if b'Invalid phone number or password' in response.content:
            print('❌ Erreur: "Invalid phone number or password"')
        elif b'csrf' in response.content.lower():
            print('❌ Erreur CSRF')
        elif b'error' in response.content.lower():
            print('❌ Autres erreurs dans la réponse')
    
    print('\n3. Test avec différents formats de numéros...')
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
        
        response = client.post(login_url, test_data)
        if response.status_code == 302:
            print(f'✓ {phone} -> Succès (redirection vers {response.url})')
        else:
            print(f'✗ {phone} -> Échec (status {response.status_code})')

if __name__ == '__main__':
    test_login_request()