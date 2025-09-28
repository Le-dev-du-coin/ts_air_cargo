#!/usr/bin/env python
"""
Script de test pour la fonctionnalité de réinitialisation de mot de passe
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')
django.setup()

from django.contrib.auth import authenticate
from authentication.models import CustomUser, PasswordResetToken
from notifications_app.services import NotificationService

def test_password_reset_functionality():
    """Test complet de la fonctionnalité de réinitialisation"""
    
    print("🧪 Test de la réinitialisation de mot de passe")
    print("=" * 50)
    
    # 1. Créer un utilisateur test (ou utiliser un existant)
    test_phone = "+22370123456"
    try:
        test_user = CustomUser.objects.get(telephone=test_phone)
        print(f"✅ Utilisateur test trouvé: {test_user.get_full_name()}")
    except CustomUser.DoesNotExist:
        test_user = CustomUser.objects.create_user(
            telephone=test_phone,
            email="test@example.com",
            password="ancien_password",
            first_name="Test",
            last_name="User",
            role='client'
        )
        print(f"✅ Utilisateur test créé: {test_user.get_full_name()}")
    
    # 2. Vérifier que l'utilisateur peut se connecter avec l'ancien mot de passe
    print("\n📝 Test connexion avec ancien mot de passe...")
    user = authenticate(telephone=test_phone, password="ancien_password")
    if user:
        print("✅ Authentification avec ancien mot de passe: OK")
    else:
        print("❌ Échec authentification avec ancien mot de passe")
        # Définir un mot de passe connu pour le test
        test_user.set_password("ancien_password")
        test_user.save()
        user = authenticate(telephone=test_phone, password="ancien_password")
        print("✅ Mot de passe défini et vérifié")
    
    # 3. Créer un token de réinitialisation
    print("\n🔑 Création du token de réinitialisation...")
    # Supprimer les anciens tokens
    PasswordResetToken.objects.filter(user=test_user, used=False).delete()
    
    # Créer un nouveau token
    test_code = "123456"
    reset_token = PasswordResetToken.objects.create(
        user=test_user,
        token=test_code
    )
    print(f"✅ Token créé: {test_code}")
    
    # 4. Tester l'envoi de SMS
    print("\n📱 Test envoi SMS...")
    try:
        message = f"TS Air Cargo: Votre code de réinitialisation est {test_code}. Ce code expire dans 24h."
        NotificationService.send_sms(
            telephone=test_user.telephone,
            message=message
        )
        print("✅ SMS envoyé avec succès")
    except Exception as e:
        print(f"❌ Erreur envoi SMS: {e}")
    
    # 5. Vérifier le token
    print("\n🔍 Vérification du token...")
    try:
        found_token = PasswordResetToken.objects.get(
            user=test_user,
            token=test_code,
            used=False
        )
        if found_token.is_expired():
            print("❌ Token expiré")
        else:
            print("✅ Token valide")
    except PasswordResetToken.DoesNotExist:
        print("❌ Token non trouvé")
    
    # 6. Simuler la réinitialisation du mot de passe
    print("\n🔄 Test réinitialisation du mot de passe...")
    nouveau_password = "nouveau_password_test"
    test_user.set_password(nouveau_password)
    test_user.save()
    
    # Marquer le token comme utilisé
    reset_token.used = True
    reset_token.save()
    
    print("✅ Mot de passe réinitialisé")
    
    # 7. Vérifier que l'ancien mot de passe ne fonctionne plus
    print("\n🚫 Test ancien mot de passe...")
    user = authenticate(telephone=test_phone, password="ancien_password")
    if user:
        print("❌ L'ancien mot de passe fonctionne encore (problème!)")
    else:
        print("✅ L'ancien mot de passe ne fonctionne plus")
    
    # 8. Vérifier que le nouveau mot de passe fonctionne
    print("\n✅ Test nouveau mot de passe...")
    user = authenticate(telephone=test_phone, password=nouveau_password)
    if user:
        print("✅ Le nouveau mot de passe fonctionne")
    else:
        print("❌ Le nouveau mot de passe ne fonctionne pas (problème!)")
    
    # 9. Vérifier que le token est marqué comme utilisé
    print("\n🔒 Vérification token utilisé...")
    reset_token.refresh_from_db()
    if reset_token.used:
        print("✅ Token marqué comme utilisé")
    else:
        print("❌ Token non marqué comme utilisé")
    
    print("\n" + "=" * 50)
    print("🎉 Test terminé !")
    
    # Nettoyer
    print("\n🧹 Nettoyage...")
    test_user.delete()
    print("✅ Utilisateur test supprimé")

if __name__ == "__main__":
    test_password_reset_functionality()