from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator

class CustomUserManager(BaseUserManager):
    """
    Manager personnalisé pour CustomUser avec authentification par téléphone
    """
    def create_user(self, telephone, email, password=None, **extra_fields):
        """
        Créer et sauvegarder un utilisateur avec téléphone, email et mot de passe
        """
        if not telephone:
            raise ValueError('Le numéro de téléphone est obligatoire')
        if not email:
            raise ValueError('L\'email est obligatoire')
        
        email = self.normalize_email(email)
        user = self.model(telephone=telephone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, telephone, email, password=None, **extra_fields):
        """
        Créer et sauvegarder un superutilisateur
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'superuser')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Un superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Un superutilisateur doit avoir is_superuser=True.')
        
        return self.create_user(telephone, email, password, **extra_fields)

class CustomUser(AbstractUser):
    """
    Modèle d'utilisateur personnalisé avec authentification par téléphone
    """
    # Supprimer le champ username par défaut
    username = None
    
    # Téléphone comme identifiant principal
    telephone = models.CharField(
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Le numéro de téléphone doit être au format: '+999999999'. Jusqu'à 15 chiffres autorisés."
            )
        ],
        help_text="Numéro de téléphone unique pour l'authentification"
    )
    
    # Rôles spécifiques selon le DEVBOOK
    role = models.CharField(
        max_length=20,
        choices=[
            ('agent_chine', 'Agent Chine'),
            ('agent_mali', 'Agent Mali'),
            ('admin_chine', 'Admin Chine'),
            ('admin_mali', 'Admin Mali'),
            ('client', 'Client'),
            ('superuser', 'Super Utilisateur'),
        ],
        default='client'
    )
    
    # Champs booléens pour les rôles (selon le DEVBOOK)
    is_agent_chine = models.BooleanField(default=False)
    is_agent_mali = models.BooleanField(default=False)
    is_admin_mali = models.BooleanField(default=False)
    is_admin_chine = models.BooleanField(default=False)
    is_client = models.BooleanField(default=True)
    
    # Manager personnalisé
    objects = CustomUserManager()
    
    # Définir le champ USERNAME_FIELD
    USERNAME_FIELD = 'telephone'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        
    def __str__(self):
        return f"{self.telephone} - {self.get_full_name()}"
    
    def save(self, *args, **kwargs):
        """
        Override save pour gérer les rôles automatiquement
        """
        # Réinitialiser tous les rôles
        self.is_agent_chine = False
        self.is_agent_mali = False
        self.is_admin_mali = False
        self.is_admin_chine = False
        self.is_client = False
        
        # Définir le rôle approprié
        if self.role == 'agent_chine':
            self.is_agent_chine = True
        elif self.role == 'agent_mali':
            self.is_agent_mali = True
        elif self.role == 'admin_mali':
            self.is_admin_mali = True
        elif self.role == 'admin_chine':
            self.is_admin_chine = True
        elif self.role == 'client':
            self.is_client = True
        elif self.role == 'superuser':
            self.is_superuser = True
            self.is_staff = True
            
        super().save(*args, **kwargs)


class PasswordResetToken(models.Model):
    """
    Modèle pour les tokens de réinitialisation de mot de passe
    """
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Token de réinitialisation"
        verbose_name_plural = "Tokens de réinitialisation"
        
    def save(self, *args, **kwargs):
        if not self.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            # Expire dans 24h
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
        
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
        
    def __str__(self):
        return f"Token for {self.user.telephone}"
