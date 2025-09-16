"""
Validators personnalisés pour TS Air Cargo
Validation des fichiers uploadés pour la sécurité
"""

import os
# import magic  # Temporairement commenté pour éviter les problèmes de dépendance
from django.core.exceptions import ValidationError
from django.conf import settings


def validate_file_size(value, max_size=10*1024*1024):
    """
    Valider la taille d'un fichier uploadé
    Par défaut: 10MB maximum
    """
    if value.size > max_size:
        size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            f'Fichier trop volumineux. Taille maximum autorisée: {size_mb}MB'
        )


def validate_image_file(value):
    """
    Valider qu'un fichier est bien une image
    """
    validate_file_size(value, max_size=5*1024*1024)  # 5MB pour images
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Format de fichier non supporté. Formats autorisés: {", ".join(valid_extensions)}'
        )


def validate_document_file(value):
    """
    Valider les documents (PDF, DOC, DOCX)
    """
    validate_file_size(value, max_size=20*1024*1024)  # 20MB pour documents
    
    valid_extensions = ['.pdf', '.doc', '.docx', '.txt']
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Format de document non supporté. Formats autorisés: {", ".join(valid_extensions)}'
        )


def validate_excel_file(value):
    """
    Valider les fichiers Excel pour l'import de données
    """
    validate_file_size(value, max_size=10*1024*1024)  # 10MB pour Excel
    
    valid_extensions = ['.xlsx', '.xls', '.csv']
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Format Excel non supporté. Formats autorisés: {", ".join(valid_extensions)}'
        )


def validate_signature_file(value):
    """
    Valider les fichiers de signature (images uniquement, taille réduite)
    """
    validate_file_size(value, max_size=2*1024*1024)  # 2MB pour signatures
    
    valid_extensions = ['.jpg', '.jpeg', '.png']
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Format de signature non supporté. Formats autorisés: {", ".join(valid_extensions)}'
        )


def validate_colis_image(value):
    """
    Validator spécifique pour les images de colis
    """
    validate_image_file(value)
    
    # Validation additionnelle: dimension minimum recommandée
    # Cette validation sera faite côté client principalement
    pass


def validate_justificatif_file(value):
    """
    Validator pour les justificatifs (documents et images acceptés)
    """
    validate_file_size(value, max_size=15*1024*1024)  # 15MB
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx']
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Format de justificatif non supporté. Formats autorisés: {", ".join(valid_extensions)}'
        )


def validate_filename_security(value):
    """
    Valider que le nom de fichier ne contient pas de caractères dangereux
    """
    filename = value.name
    dangerous_chars = ['..', '/', '\\', '<', '>', '|', ':', '*', '?', '"']
    
    for char in dangerous_chars:
        if char in filename:
            raise ValidationError(
                'Le nom de fichier contient des caractères non autorisés'
            )
    
    if len(filename) > 255:
        raise ValidationError(
            'Le nom de fichier est trop long (maximum 255 caractères)'
        )