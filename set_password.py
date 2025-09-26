#!/usr/bin/env python
"""
Script pour définir un mot de passe connu pour les tests
"""

import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from authentication.models import CustomUser
from django.contrib.auth import authenticate

def set_passwords():
    print('=== Définition de mots de passe connus pour les tests ===')
    
    # Définir des mots de passe connus
    test_password = 'test123456'
    
    # Pour chaque utilisateur, définir le même mot de passe test
    users = CustomUser.objects.all()
    for user in users:
        user.set_password(test_password)
        user.save()
        print(f'Mot de passe défini pour {user.telephone} ({user.role})')
    
    print(f'\n=== Test d\'authentification avec le mot de passe: {test_password} ===')
    
    # Tester l'authentification pour chaque utilisateur
    for user in users:
        auth_user = authenticate(telephone=user.telephone, password=test_password)
        if auth_user:
            print(f'✓ {user.telephone} - Authentification réussie')
        else:
            print(f'✗ {user.telephone} - Échec authentification')

if __name__ == '__main__':
    set_passwords()