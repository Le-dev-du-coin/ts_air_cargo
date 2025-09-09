from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
import string

User = get_user_model()

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telephone = models.CharField(max_length=20, unique=True)
    nom_complet = models.CharField(max_length=255)
    adresse = models.TextField(blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    pays = models.CharField(max_length=100, default='Mali')
    is_verified = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.nom_complet} ({self.telephone})"
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"


class ClientNotificationSettings(models.Model):
    """
    Paramètres de notification pour les clients
    """
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='notification_settings')
    notifications_in_app = models.BooleanField(default=True, verbose_name="Notifications in-app")
    notifications_whatsapp = models.BooleanField(default=False, verbose_name="Notifications WhatsApp")
    notifications_sms = models.BooleanField(default=False, verbose_name="Notifications SMS")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Paramètres de {self.client.nom_complet}"
    
    class Meta:
        verbose_name = "Paramètres de notification"
        verbose_name_plural = "Paramètres de notification"


class OTPVerification(models.Model):
    telephone = models.CharField(max_length=20)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)  # OTP expire après 5 minutes
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        return not self.is_used and not self.is_expired()
    
    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))
    
    def __str__(self):
        return f"OTP {self.otp_code} pour {self.telephone}"
    
    class Meta:
        verbose_name = "Code OTP"
        verbose_name_plural = "Codes OTP"
        ordering = ['-created_at']
