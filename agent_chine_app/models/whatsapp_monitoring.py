"""
Modèles pour le monitoring des notifications WhatsApp dans l'app agent_chine
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class WhatsAppMessageAttempt(models.Model):
    """
    Suivi des tentatives d'envoi de messages WhatsApp avec retry
    """
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sending', 'En cours d\'envoi'),
        ('sent', 'Envoyé'),
        ('delivered', 'Livré'),
        ('read', 'Lu'),
        ('failed', 'Échec'),
        ('failed_retry', 'Échec - Retry programmé'),
        ('failed_final', 'Échec définitif'),
        ('cancelled', 'Annulé'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('account', 'Création de compte'),
        ('otp', 'Code OTP'),
        ('system', 'Message système'),
        ('notification', 'Notification générale'),
        ('urgent', 'Notification urgente'),
        ('report', 'Rapport'),
        ('colis_status', 'Statut colis'),
        ('lot_status', 'Statut lot'),
        ('other', 'Autre'),
    ]
    
    PRIORITY_CHOICES = [
        (1, 'Très haute'),
        (2, 'Haute'),
        (3, 'Normale'),
        (4, 'Basse'),
        (5, 'Très basse'),
    ]
    
    # Informations de base
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_attempts',
        help_text="Utilisateur destinataire du message"
    )
    
    phone_number = models.CharField(
        max_length=20,
        help_text="Numéro de téléphone de destination (avec indicatif)"
    )
    
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default='notification',
        help_text="Type de message"
    )
    
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Catégorie spécifique du message"
    )
    
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Priorité du message (1=très haute, 5=très basse)"
    )
    
    # Contenu du message
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Titre du message"
    )
    
    message_content = models.TextField(
        help_text="Contenu du message à envoyer"
    )
    
    # Statut et tentatives
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Statut actuel du message"
    )
    
    attempt_count = models.IntegerField(
        default=0,
        help_text="Nombre de tentatives d'envoi"
    )
    
    max_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Nombre maximum de tentatives"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de création"
    )
    
    first_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de la première tentative"
    )
    
    last_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de la dernière tentative"
    )
    
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure du prochain retry"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure d'envoi réussi"
    )
    
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de livraison confirmée"
    )
    
    # Informations de livraison
    provider_message_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID du message chez le provider (WaChap)"
    )
    
    provider_response = models.JSONField(
        default=dict,
        help_text="Réponse complète du provider"
    )
    
    # Informations d'erreur
    error_message = models.TextField(
        blank=True,
        help_text="Message d'erreur de la dernière tentative"
    )
    
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Code d'erreur du provider"
    )
    
    # Métadonnées
    sender_role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Rôle de l'expéditeur (pour sélection instance WaChap)"
    )
    
    region_override = models.CharField(
        max_length=20,
        blank=True,
        help_text="Région forcée (chine/mali)"
    )
    
    context_data = models.JSONField(
        default=dict,
        help_text="Données contextuelles additionnelles"
    )
    
    # Gestion des retries
    retry_delay_seconds = models.IntegerField(
        default=300,  # 5 minutes
        help_text="Délai entre les tentatives (en secondes)"
    )
    
    exponential_backoff = models.BooleanField(
        default=True,
        help_text="Utiliser un délai exponentiel entre les retries"
    )
    
    class Meta:
        db_table = 'agent_chine_whatsapp_monitoring'
        verbose_name = "Tentative WhatsApp"
        verbose_name_plural = "Tentatives WhatsApp"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['phone_number', 'created_at']),
            models.Index(fields=['next_retry_at']),
            models.Index(fields=['status', 'priority', 'created_at']),
        ]
    
    def __str__(self):
        user_info = f"({self.user.get_full_name()})" if self.user else ""
        return f"{self.phone_number} {user_info} - {self.get_message_type_display()} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement le délai du prochain retry
        if self.status == 'failed_retry' and not self.next_retry_at:
            self.calculate_next_retry()
        
        super().save(*args, **kwargs)
    
    def calculate_next_retry(self):
        """
        Calcule la date du prochain retry en fonction du nombre de tentatives
        """
        if self.exponential_backoff:
            # Délai exponentiel: base_delay * (2 ^ attempt_count)
            delay = self.retry_delay_seconds * (2 ** min(self.attempt_count, 5))  # Max 2^5 = 32x
        else:
            # Délai fixe
            delay = self.retry_delay_seconds
        
        self.next_retry_at = timezone.now() + timezone.timedelta(seconds=delay)
    
    def can_retry(self):
        """
        Vérifie si une nouvelle tentative est possible
        """
        return (
            self.status in ['pending', 'failed', 'failed_retry'] and
            self.attempt_count < self.max_attempts and
            (not self.next_retry_at or self.next_retry_at <= timezone.now())
        )
    
    def should_retry_now(self):
        """
        Vérifie si le message doit être retenté maintenant
        """
        return (
            self.status == 'failed_retry' and
            self.next_retry_at and
            self.next_retry_at <= timezone.now() and
            self.attempt_count < self.max_attempts
        )
    
    def mark_as_sending(self):
        """
        Marque le message comme en cours d'envoi
        """
        self.status = 'sending'
        self.attempt_count += 1
        if not self.first_attempt_at:
            self.first_attempt_at = timezone.now()
        self.last_attempt_at = timezone.now()
        self.save()
    
    def mark_as_sent(self, provider_message_id=None, provider_response=None):
        """
        Marque le message comme envoyé avec succès
        """
        self.status = 'sent'
        self.sent_at = timezone.now()
        if provider_message_id:
            self.provider_message_id = provider_message_id
        if provider_response:
            self.provider_response = provider_response
        self.next_retry_at = None
        self.save()
    
    def mark_as_failed(self, error_message=None, error_code=None, final=False):
        """
        Marque le message comme échoué
        
        Args:
            error_message: Message d'erreur
            error_code: Code d'erreur
            final: Si True, marque comme échec définitif sans retry
        """
        if error_message:
            self.error_message = error_message
        if error_code:
            self.error_code = error_code
        
        if final or self.attempt_count >= self.max_attempts:
            self.status = 'failed_final'
            self.next_retry_at = None
        else:
            self.status = 'failed_retry'
            self.calculate_next_retry()
        
        self.save()
    
    def mark_as_delivered(self):
        """
        Marque le message comme livré (webhook du provider)
        """
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()
    
    def cancel(self):
        """
        Annule le message (plus de tentatives)
        """
        self.status = 'cancelled'
        self.next_retry_at = None
        self.save()
    
    @property
    def is_final_status(self):
        """
        Vérifie si le message est dans un état final
        """
        return self.status in ['sent', 'delivered', 'read', 'failed_final', 'cancelled']
    
    @property
    def total_delay_seconds(self):
        """
        Calcule le délai total entre la création et l'envoi/échec final
        """
        if not self.sent_at and not self.is_final_status:
            return None
        
        end_time = self.sent_at or self.last_attempt_at or timezone.now()
        return int((end_time - self.created_at).total_seconds())
    
    @classmethod
    def get_pending_retries(cls):
        """
        Retourne les messages prêts pour retry
        """
        now = timezone.now()
        return cls.objects.filter(
            status='failed_retry',
            next_retry_at__lte=now,
            attempt_count__lt=models.F('max_attempts')
        ).order_by('priority', 'next_retry_at')
    
    @classmethod
    def get_stats_summary(cls):
        """
        Retourne des statistiques rapides
        """
        from django.db.models import Count, Q
        
        stats = cls.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            failed_final=Count('id', filter=Q(status='failed_final')),
            failed_retry=Count('id', filter=Q(status='failed_retry')),
        )
        
        return stats


class WhatsAppWebhookLog(models.Model):
    """
    Log des webhooks reçus des providers WhatsApp
    """
    
    message_attempt = models.ForeignKey(
        WhatsAppMessageAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhooks'
    )
    
    provider_message_id = models.CharField(
        max_length=100,
        help_text="ID du message chez le provider"
    )
    
    webhook_type = models.CharField(
        max_length=50,
        help_text="Type de webhook (status, delivery, read, etc.)"
    )
    
    status = models.CharField(
        max_length=50,
        help_text="Statut reporté par le webhook"
    )
    
    raw_payload = models.JSONField(
        help_text="Payload brute du webhook"
    )
    
    processed = models.BooleanField(
        default=False,
        help_text="Webhook traité et appliqué"
    )
    
    processing_error = models.TextField(
        blank=True,
        help_text="Erreur lors du traitement"
    )
    
    received_at = models.DateTimeField(
        auto_now_add=True
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'agent_chine_whatsapp_webhooks'
        verbose_name = "Webhook WhatsApp"
        verbose_name_plural = "Webhooks WhatsApp"
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['provider_message_id']),
            models.Index(fields=['processed', 'received_at']),
        ]
    
    def __str__(self):
        return f"Webhook {self.webhook_type} - {self.provider_message_id} - {self.status}"