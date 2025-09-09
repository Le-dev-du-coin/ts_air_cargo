from django.db import models
from django.conf import settings
from django.utils import timezone

class Notification(models.Model):
    """
    Modèle pour gérer toutes les notifications (SMS, WhatsApp, In-App)
    """
    TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('in_app', 'In-App'),
        ('email', 'Email'),
    ]
    
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('envoye', 'Envoyé'),
        ('echec', 'Échec'),
        ('lu', 'Lu'),
    ]
    
    CATEGORIE_CHOICES = [
        ('colis_cree', 'Colis créé'),
        ('lot_expedie', 'Lot expédié'),
        ('colis_en_transit', 'Colis en transit'),
        ('colis_arrive', 'Colis arrivé'),
        ('colis_livre', 'Colis livré'),
        ('transfert_argent', 'Transfert d\'argent'),
        ('transfert_recu', 'Transfert reçu'),
        ('reception_lot', 'Réception de lot'),
        ('rapport_operationnel', 'Rapport opérationnel'),
        ('alerte_systeme', 'Alerte système'),
        ('information_generale', 'Information générale'),
    ]
    
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications_recues',
        help_text="Utilisateur destinataire de la notification"
    )
    
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_envoyees',
        help_text="Utilisateur qui a envoyé la notification (si applicable)"
    )
    
    type_notification = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        help_text="Type de notification"
    )
    
    categorie = models.CharField(
        max_length=30,
        choices=CATEGORIE_CHOICES,
        help_text="Catégorie de la notification"
    )
    
    titre = models.CharField(
        max_length=200,
        help_text="Titre de la notification"
    )
    
    message = models.TextField(
        help_text="Contenu du message"
    )
    
    lien_action = models.URLField(
        blank=True,
        help_text="Lien vers une action (optionnel)"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='en_attente'
    )
    
    # Références aux objets liés
    colis_reference = models.ForeignKey(
        'agent_chine_app.Colis',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Référence au colis (si applicable)"
    )
    
    lot_reference = models.ForeignKey(
        'agent_chine_app.Lot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Référence au lot (si applicable)"
    )
    
    transfert_reference = models.ForeignKey(
        'admin_mali_app.TransfertArgent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Référence au transfert d'argent (si applicable)"
    )
    
    # Métadonnées pour l'envoi
    telephone_destinataire = models.CharField(
        max_length=20,
        blank=True,
        help_text="Numéro de téléphone pour SMS/WhatsApp"
    )
    
    email_destinataire = models.EmailField(
        blank=True,
        help_text="Email pour les notifications email"
    )
    
    # Dates et statuts
    date_creation = models.DateTimeField(auto_now_add=True)
    date_envoi = models.DateTimeField(null=True, blank=True)
    date_lecture = models.DateTimeField(null=True, blank=True)
    
    # Résultats d'envoi
    message_id_externe = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID du message du service externe (WaChap, Orange SMS, etc.)"
    )
    
    erreur_envoi = models.TextField(
        blank=True,
        help_text="Détails de l'erreur en cas d'échec d'envoi"
    )
    
    nombre_tentatives = models.IntegerField(
        default=0,
        help_text="Nombre de tentatives d'envoi"
    )
    
    prochaine_tentative = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la prochaine tentative d'envoi"
    )
    
    priorite = models.IntegerField(
        default=1,
        help_text="Priorité de la notification (1=haute, 5=basse)"
    )
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['destinataire', 'statut']),
            models.Index(fields=['type_notification', 'statut']),
            models.Index(fields=['date_creation']),
        ]
        
    def __str__(self):
        return f"{self.titre} - {self.destinataire.get_full_name()} - {self.statut}"
    
    def marquer_comme_lu(self):
        """
        Marquer la notification comme lue
        """
        if self.statut == 'envoye':
            self.statut = 'lu'
            self.date_lecture = timezone.now()
            self.save(update_fields=['statut', 'date_lecture'])
    
    def marquer_comme_envoye(self, message_id=None):
        """
        Marquer la notification comme envoyée
        """
        self.statut = 'envoye'
        self.date_envoi = timezone.now()
        if message_id:
            self.message_id_externe = message_id
        self.save(update_fields=['statut', 'date_envoi', 'message_id_externe'])
    
    def marquer_comme_echec(self, erreur=None):
        """
        Marquer la notification comme échouée
        """
        self.statut = 'echec'
        self.nombre_tentatives += 1
        if erreur:
            self.erreur_envoi = erreur
        # Programmer une nouvelle tentative dans 30 minutes
        self.prochaine_tentative = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=['statut', 'nombre_tentatives', 'erreur_envoi', 'prochaine_tentative'])

class ConfigurationNotification(models.Model):
    """
    Configuration globale pour les notifications avec WaChap et Orange SMS API
    """
    nom_configuration = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nom de la configuration"
    )
    
    # Configuration SMS via Orange SMS API
    sms_active = models.BooleanField(default=True)
    orange_sms_api_key = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Clé API Orange SMS"
    )
    orange_sms_api_url = models.URLField(
        blank=True,
        help_text="URL de l'API Orange SMS"
    )
    orange_sms_sender_id = models.CharField(
        max_length=50, 
        blank=True,
        help_text="ID de l'expéditeur pour Orange SMS"
    )
    
    # Configuration WhatsApp via WaChap (ancienne config Twilio désactivée)
    whatsapp_active = models.BooleanField(default=False, help_text="Ancienne config - Utiliser WaChap maintenant")
    twilio_account_sid = models.CharField(
        max_length=200, 
        blank=True,
        help_text="[OBSOLÈTE] Ancien SID Twilio - Migration vers WaChap terminée"
    )
    twilio_auth_token = models.CharField(
        max_length=200, 
        blank=True,
        help_text="[OBSOLÈTE] Ancien token Twilio - Migration vers WaChap terminée"
    )
    twilio_whatsapp_number = models.CharField(
        max_length=20, 
        blank=True,
        help_text="[OBSOLÈTE] Ancien numéro Twilio - Migration vers WaChap terminée"
    )
    
    # Configuration Email
    email_active = models.BooleanField(default=True)
    email_smtp_host = models.CharField(
        max_length=200, 
        blank=True,
        default='smtp.gmail.com'
    )
    email_smtp_port = models.IntegerField(default=587)
    email_smtp_user = models.CharField(max_length=200, blank=True)
    email_smtp_password = models.CharField(max_length=200, blank=True)
    email_use_tls = models.BooleanField(default=True)
    
    # Configuration WaChap - Instance Chine
    wachap_chine_active = models.BooleanField(
        default=True,
        help_text="Activer l'instance WaChap Chine"
    )
    wachap_chine_access_token = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Token d'accès WaChap pour l'instance Chine"
    )
    wachap_chine_instance_id = models.CharField(
        max_length=200, 
        blank=True,
        help_text="ID d'instance WaChap Chine"
    )
    wachap_chine_webhook_url = models.URLField(
        blank=True,
        help_text="URL webhook pour l'instance Chine (optionnel)"
    )
    
    # Configuration WaChap - Instance Mali
    wachap_mali_active = models.BooleanField(
        default=True,
        help_text="Activer l'instance WaChap Mali"
    )
    wachap_mali_access_token = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Token d'accès WaChap pour l'instance Mali"
    )
    wachap_mali_instance_id = models.CharField(
        max_length=200, 
        blank=True,
        help_text="ID d'instance WaChap Mali"
    )
    wachap_mali_webhook_url = models.URLField(
        blank=True,
        help_text="URL webhook pour l'instance Mali (optionnel)"
    )
    
    # Paramètres généraux
    max_tentatives_envoi = models.IntegerField(
        default=3,
        help_text="Nombre maximum de tentatives d'envoi"
    )
    delai_entre_tentatives = models.IntegerField(
        default=30,
        help_text="Délai en minutes entre les tentatives"
    )
    
    # Templates de messages par défaut
    template_colis_cree = models.TextField(
        default="Votre colis {numero_suivi} a été enregistré dans notre système et sera bientôt expédié. Merci de faire confiance à TS Air Cargo.",
        help_text="Template pour la création de colis"
    )
    
    template_lot_expedie = models.TextField(
        default="Votre colis {numero_suivi} a été expédié dans le lot {numero_lot}. Suivez son statut sur notre plateforme TS Air Cargo.",
        help_text="Template pour l'expédition de lot"
    )
    
    template_colis_arrive = models.TextField(
        default="Bonne nouvelle ! Votre colis {numero_suivi} est arrivé au Mali. Nous vous contacterons pour la livraison.",
        help_text="Template pour l'arrivée de colis"
    )
    
    template_colis_livre = models.TextField(
        default="Votre colis {numero_suivi} a été livré avec succès. Merci d'avoir choisi TS Air Cargo.",
        help_text="Template pour la livraison de colis"
    )
    
    active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuration Notification"
        verbose_name_plural = "Configurations Notifications"
        
    def __str__(self):
        return self.nom_configuration


class NotificationTask(models.Model):
    """
    Modèle pour tracker les tâches Celery de notifications avec monitoring avancé
    Spécialisé pour les notifications de masse et le suivi par lot
    """
    TASK_STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('STARTED', 'En cours'),
        ('SUCCESS', 'Terminé avec succès'),
        ('FAILURE', 'Échec'),
        ('RETRY', 'En cours de retry'),
        ('REVOKED', 'Annulé'),
    ]
    
    TASK_TYPE_CHOICES = [
        ('individual', 'Notification individuelle'),
        ('bulk_lot_closed', 'Notifications lot fermé'),
        ('bulk_lot_shipped', 'Notifications lot expédié'),
        ('bulk_lot_arrived', 'Notifications lot arrivé'),
        ('bulk_lot_delivered', 'Notifications lot livré'),
        ('bulk_custom', 'Notifications personnalisées en masse'),
    ]
    
    # Métadonnées de la tâche Celery
    task_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID unique de la tâche Celery"
    )
    
    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPE_CHOICES,
        help_text="Type de tâche de notification"
    )
    
    task_status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='PENDING',
        help_text="Statut actuel de la tâche"
    )
    
    # Relations avec les objets métier
    lot_reference = models.ForeignKey(
        'agent_chine_app.Lot',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Lot concerné pour les notifications de masse"
    )
    
    colis_reference = models.ForeignKey(
        'agent_chine_app.Colis',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Colis concerné pour les notifications individuelles"
    )
    
    client_reference = models.ForeignKey(
        'agent_chine_app.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Client concerné (pour notifications individuelles)"
    )
    
    # Informations sur la tâche
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Utilisateur qui a déclenché la tâche"
    )
    
    # Statistiques d'exécution
    total_notifications = models.IntegerField(
        default=0,
        help_text="Nombre total de notifications à envoyer"
    )
    
    notifications_sent = models.IntegerField(
        default=0,
        help_text="Nombre de notifications envoyées avec succès"
    )
    
    notifications_failed = models.IntegerField(
        default=0,
        help_text="Nombre de notifications échouées"
    )
    
    retry_count = models.IntegerField(
        default=0,
        help_text="Nombre de tentatives de retry"
    )
    
    # Métadonnées temporelles
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Résultats et erreurs
    result_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Données de résultat de la tâche (JSON)"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Message d'erreur en cas d'échec"
    )
    
    # Configuration de la tâche
    message_template = models.TextField(
        blank=True,
        help_text="Template du message utilisé"
    )
    
    notification_method = models.CharField(
        max_length=20,
        default='whatsapp',
        help_text="Méthode de notification (whatsapp, sms, email)"
    )
    
    priority = models.IntegerField(
        default=5,
        help_text="Priorité de la tâche (1=haute, 10=basse)"
    )
    
    class Meta:
        verbose_name = "Tâche de Notification"
        verbose_name_plural = "Tâches de Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['task_status', 'created_at']),
            models.Index(fields=['lot_reference', 'task_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        if self.lot_reference:
            return f"{self.get_task_type_display()} - Lot {self.lot_reference.numero_lot} - {self.get_task_status_display()}"
        elif self.client_reference:
            return f"{self.get_task_type_display()} - {self.client_reference.user.get_full_name()} - {self.get_task_status_display()}"
        return f"Tâche {self.task_id} - {self.get_task_status_display()}"
    
    @property
    def success_rate(self):
        """Calcule le taux de succès des notifications"""
        if self.total_notifications == 0:
            return 0
        return (self.notifications_sent / self.total_notifications) * 100
    
    @property
    def is_completed(self):
        """Vérifie si la tâche est terminée"""
        return self.task_status in ['SUCCESS', 'FAILURE', 'REVOKED']
    
    @property
    def duration(self):
        """Calcule la durée d'exécution si terminée"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    def mark_as_started(self):
        """Marquer la tâche comme démarrée"""
        self.task_status = 'STARTED'
        self.started_at = timezone.now()
        self.save(update_fields=['task_status', 'started_at'])
    
    def mark_as_completed(self, success=True, result_data=None, error_message=None):
        """Marquer la tâche comme terminée"""
        self.task_status = 'SUCCESS' if success else 'FAILURE'
        self.completed_at = timezone.now()
        if result_data:
            self.result_data = result_data
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['task_status', 'completed_at', 'result_data', 'error_message'])
    
    def update_progress(self, sent_count=None, failed_count=None):
        """Mettre à jour les statistiques de progression"""
        if sent_count is not None:
            self.notifications_sent = sent_count
        if failed_count is not None:
            self.notifications_failed = failed_count
        self.save(update_fields=['notifications_sent', 'notifications_failed'])
