"""
Utilitaires pour l'authentification
"""
import re
from django.core.exceptions import ValidationError


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalise un numéro de téléphone au format international standard.
    
    Formats acceptés:
    - Mali: +223XXXXXXXX ou XXXXXXXX (8 chiffres commençant par 6 ou 7)
    - Chine: +8613XXXXXXXXX ou 13XXXXXXXXX (11 chiffres commençant par 1)
    
    Args:
        phone_number: Le numéro de téléphone brut
        
    Returns:
        Le numéro normalisé avec l'indicatif pays (+223 ou +86)
        
    Raises:
        ValidationError: Si le format du numéro est invalide
    """
    if not phone_number:
        raise ValidationError("Le numéro de téléphone est requis")
    
    # Supprimer tous les caractères non-numériques sauf le +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Si commence déjà par +, valider le format
    if cleaned.startswith('+'):
        # Numéro malien: +223 + 8 chiffres
        if re.match(r'^\+223[67]\d{7}$', cleaned):
            return cleaned
        # Numéro chinois: +86 + 11 chiffres commençant par 1
        elif re.match(r'^\+861[3-9]\d{9}$', cleaned):
            return cleaned
        else:
            raise ValidationError(
                f"Format de numéro invalide: {phone_number}. "
                "Formats acceptés: +223XXXXXXXX (Mali) ou +8613XXXXXXXXX (Chine)"
            )
    
    # Sans +, deviner le pays selon le format
    # Numéro malien: 8 chiffres commençant par 6 ou 7
    if re.match(r'^[67]\d{7}$', cleaned):
        return '+223' + cleaned
    
    # Numéro chinois: 11 chiffres commençant par 1
    elif re.match(r'^1[3-9]\d{9}$', cleaned):
        return '+86' + cleaned
    
    # Commence par 223 (malien sans +)
    elif cleaned.startswith('223') and re.match(r'^223[67]\d{7}$', cleaned):
        return '+' + cleaned
    
    # Commence par 86 (chinois sans +)
    elif cleaned.startswith('86') and re.match(r'^861[3-9]\d{9}$', cleaned):
        return '+' + cleaned
    
    # Format non reconnu
    raise ValidationError(
        f"Format de numéro invalide: {phone_number}. "
        "Formats acceptés: +223XXXXXXXX (Mali) ou +8613XXXXXXXXX (Chine)"
    )


def validate_phone_unique(phone_number: str, exclude_user_id: int = None) -> None:
    """
    Vérifie qu'un numéro de téléphone n'existe pas déjà dans la base de données.
    
    Args:
        phone_number: Le numéro de téléphone normalisé à vérifier
        exclude_user_id: ID de l'utilisateur à exclure de la vérification (pour l'édition)
        
    Raises:
        ValidationError: Si le numéro existe déjà
    """
    from authentication.models import CustomUser
    
    # Normaliser le numéro avant vérification
    normalized = normalize_phone_number(phone_number)
    
    # Vérifier l'existence
    query = CustomUser.objects.filter(telephone=normalized)
    if exclude_user_id:
        query = query.exclude(id=exclude_user_id)
    
    if query.exists():
        raise ValidationError(
            f"Ce numéro de téléphone ({normalized}) est déjà enregistré dans le système."
        )
