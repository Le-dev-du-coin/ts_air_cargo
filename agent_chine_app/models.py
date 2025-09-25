from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
from ts_air_cargo.validators import validate_colis_image, validate_filename_security

class Client(models.Model):
    """
    Modèle Client selon les spécifications du DEVBOOK
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile'
    )
    adresse = models.TextField(help_text="Adresse complète du client")
    pays = models.CharField(
        max_length=100,
        choices=[
            ('ML', 'Mali'),
            ('SN', 'Sénégal'),
            ('CI', "Côte d'Ivoire"),
            ('BF', 'Burkina Faso'),
            ('NE', 'Niger'),
            ('GN', 'Guinée'),
            ('MR', 'Mauritanie'),
            ('GM', 'Gambie'),
            ('GW', 'Guinée-Bissau'),
        ],
        default='ML'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.pays}"

class Lot(models.Model):
    """
    Modèle Lot pour grouper les colis selon le DEVBOOK
    """
    STATUS_CHOICES = [
        ('ouvert', 'Ouvert'),
        ('ferme', 'Fermé'),
        ('expedie', 'Expédié'),
        ('en_transit', 'En Transit'),
        ('arrive', 'Arrivé au Mali'),
        ('livre', 'Livré'),
    ]
    
    TRANSPORT_CHOICES = [
        ('cargo', 'Cargo'),
        ('express', 'Express'),
        ('bateau', 'Bateau'),
    ]
    
    numero_lot = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        help_text="Numéro auto-généré: TYPE-YYYYMMDDXXX"
    )
    type_lot = models.CharField(
        max_length=20,
        choices=TRANSPORT_CHOICES,
        default='cargo',
        help_text="Type de transport principal du lot"
    )
    prix_transport = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix total du transport du lot"
    )
    frais_douane = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Frais de douane saisis par l'agent Mali"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ouvert'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_fermeture = models.DateTimeField(null=True, blank=True)
    date_expedition = models.DateTimeField(null=True, blank=True)
    date_arrivee = models.DateTimeField(null=True, blank=True)
    
    agent_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lots_crees'
    )
    
    class Meta:
        verbose_name = "Lot"
        verbose_name_plural = "Lots"
        ordering = ['-date_creation']
        
    def save(self, *args, **kwargs):
        if not self.numero_lot:
            # Générer numéro de lot avec type: TYPE-YYYYMMDDXXX
            date_str = timezone.now().strftime('%Y%m%d')
            type_prefix = self.type_lot.upper()
            
            count = Lot.objects.filter(
                numero_lot__startswith=f"{type_prefix}-{date_str}"
            ).count() + 1
            
            self.numero_lot = f"{type_prefix}-{date_str}{count:03d}"
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Lot {self.numero_lot} - {self.statut}"

class Colis(models.Model):
    """
    Modèle Colis selon les spécifications du DEVBOOK
    """
    STATUS_CHOICES = [
        ('en_attente', 'En Attente'),
        ('receptionne_chine', 'Réceptionné en Chine'),
        ('en_transit', 'En Transit'),
        ('arrive', 'Arrivé au Mali'),
        ('livre', 'Livré'),
        ('perdu', 'Perdu'),
    ]
    
    PAYMENT_CHOICES = [
        ('paye_chine', 'Payé en Chine'),
        ('paye_mali', 'Payé au Mali'),
        ('non_paye', 'Non Payé'),
    ]
    
    TRANSPORT_CHOICES = [
        ('cargo', 'Cargo'),
        ('express', 'Express'),
        ('bateau', 'Bateau'),
    ]
    
    numero_suivi = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Numéro de suivi auto-généré: TS..."
    )
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='colis'
    )
    
    lot = models.ForeignKey(
        Lot,
        on_delete=models.CASCADE,
        related_name='colis'
    )
    
    # Type de transport
    type_transport = models.CharField(
        max_length=20,
        choices=TRANSPORT_CHOICES,
        default='cargo',
        help_text="Type de transport: Cargo/Express (par poids) ou Bateau (par dimensions)"
    )
    
    # Image du colis
    image = models.ImageField(
        upload_to='colis_images/',
        null=True,
        blank=True,
        validators=[validate_colis_image, validate_filename_security],
        help_text="Photo du colis (max 5MB, formats: JPG, PNG, GIF, WebP)"
    )
    
    # Dimensions selon le DEVBOOK
    longueur = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Longueur en cm"
    )
    largeur = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Largeur en cm"
    )
    hauteur = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Hauteur en cm"
    )
    
    poids = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Poids en kg"
    )
    
    prix_calcule = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        help_text="Prix calculé automatiquement"
    )
    
    mode_paiement = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default='non_paye'
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='receptionne_chine'
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description du contenu du colis"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Colis"
        verbose_name_plural = "Colis"
        ordering = ['-date_creation']
        
    def save(self, *args, **kwargs):
        if not self.numero_suivi:
            # Générer numéro de suivi: TS + UUID court
            unique_id = str(uuid.uuid4())[:8].upper()
            self.numero_suivi = f"TS{unique_id}"
            
        # Calculer le prix automatiquement
        if not self.prix_calcule:
            self.prix_calcule = self.calculer_prix_automatique()
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.numero_suivi} - {self.client}"
    
    def volume_m3(self):
        """
        Calculer le volume en mètres cubes
        """
        return (self.longueur * self.largeur * self.hauteur) / 1000000  # cm3 vers m3
    
    def calculer_prix_automatique(self):
        """
        Calculer le prix automatiquement selon les tarifs configurés
        Le calcul dépend du type de transport:
        - Cargo/Express: basé sur le poids
        - Bateau: basé sur les dimensions (volume)
        """
        try:
            from reporting_app.models import ShippingPrice
            
            # Récupérer les tarifs actifs
            tarifs = ShippingPrice.objects.filter(
                actif=True,
                pays_destination__in=[self.client.pays, 'ALL']
            )
            
            prix_max = 0
            volume_m3 = self.volume_m3()
            
            for tarif in tarifs:
                if self.type_transport in ['cargo', 'express']:
                    # Pour Cargo et Express, utiliser le poids principalement
                    prix_calcule = tarif.calculer_prix(float(self.poids), volume_m3)
                else:  # bateau
                    # Pour Bateau, utiliser principalement le volume
                    prix_calcule = tarif.calculer_prix(float(self.poids), volume_m3)
                    # Majorer pour le transport par bateau (généralement moins cher mais plus lent)
                    prix_calcule *= 0.8
                    
                if prix_calcule > prix_max:
                    prix_max = prix_calcule
            
            # Prix de base selon le type de transport si aucun tarif trouvé
            if prix_max == 0:
                if self.type_transport in ['cargo', 'express']:
                    # Prix basé sur le poids
                    multiplier = 12000 if self.type_transport == 'express' else 10000
                    prix_max = float(self.poids) * multiplier
                else:  # bateau
                    # Prix basé sur le volume
                    prix_max = volume_m3 * 300000  # 50 000 CFA par m³
                    
            return max(prix_max, 1000)  # Prix minimum de 1000 CFA
            
        except Exception as e:
            # En cas d'erreur, retourner un prix basique
            if self.type_transport in ['cargo', 'express']:
                return float(self.poids) * 10000
            else:
                return self.volume_m3() * 300000


class ColisCreationTask(models.Model):
    """
    Tâche de création/modification de colis en arrière-plan
    Permet un traitement asynchrone pour améliorer les performances
    """
    TASK_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('image_uploading', 'Upload image...'),
        ('price_calculating', 'Calcul prix...'),
        ('notification_sending', 'Envoi notification...'),
        ('completed', 'Finalisé'),
        ('failed', 'Échec'),
        ('failed_retry', 'Échec - retry programmé'),
        ('failed_final', 'Échec définitif'),
        ('cancelled', 'Annulé'),
    ]
    
    OPERATION_CHOICES = [
        ('create', 'Création'),
        ('update', 'Modification'),
    ]
    
    # Identification de la tâche
    task_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Identifiant unique de la tâche"
    )
    celery_task_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID de la tâche Celery"
    )
    operation_type = models.CharField(
        max_length=10,
        choices=OPERATION_CHOICES,
        help_text="Type d'opération (création ou modification)"
    )
    
    # État de la tâche
    status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='pending',
        help_text="État actuel de la tâche"
    )
    current_step = models.CharField(
        max_length=100,
        blank=True,
        help_text="Étape en cours de traitement"
    )
    progress_percentage = models.IntegerField(
        default=0,
        help_text="Pourcentage de progression (0-100)"
    )
    
    # Données du colis (JSON)
    colis_data = models.JSONField(
        help_text="Données du formulaire colis sérialisées en JSON"
    )
    original_image_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Chemin vers l'image temporaire"
    )
    
    # Relations
    colis = models.ForeignKey(
        'Colis',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Colis créé (null pendant le traitement)"
    )
    lot = models.ForeignKey(
        'Lot',
        on_delete=models.CASCADE,
        help_text="Lot de destination"
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text="Agent qui a initié la tâche"
    )
    
    # Gestion des erreurs
    error_message = models.TextField(
        blank=True,
        help_text="Message d'erreur en cas d'échec"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Nombre de tentatives effectuées"
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Nombre maximum de tentatives"
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la prochaine tentative"
    )
    
    # Métadonnées temporelles
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de la tâche"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de début de traitement"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de fin de traitement"
    )
    
    class Meta:
        verbose_name = "Tâche de Colis"
        verbose_name_plural = "Tâches de Colis"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['initiated_by', 'status']),
            models.Index(fields=['lot', 'status']),
        ]
        
    def __str__(self):
        return f"Tâche {self.task_id} - {self.get_status_display()}"
    
    def can_retry(self):
        """
        Vérifie si la tâche peut être relancée
        """
        return (
            self.retry_count < self.max_retries and 
            self.status in ['failed', 'failed_retry']
        )
    
    def get_duration(self):
        """
        Calcule la durée de traitement si la tâche est terminée
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    def get_estimated_completion_time(self):
        """
        Estimation du temps restant basée sur l'historique
        """
        if self.status == 'completed':
            return None
            
        # Moyenne des tâches similaires récentes
        similar_tasks = ColisCreationTask.objects.filter(
            operation_type=self.operation_type,
            status='completed',
            completed_at__isnull=False,
            started_at__isnull=False
        ).order_by('-completed_at')[:10]
        
        if similar_tasks.exists():
            total_duration = sum([
                (task.completed_at - task.started_at).total_seconds() 
                for task in similar_tasks
            ])
            avg_duration = total_duration / similar_tasks.count()
            return avg_duration
        
        # Estimation par défaut selon le type d'opération
        return 45.0 if self.operation_type == 'create' else 30.0
    
    def mark_as_started(self):
        """
        Marque la tâche comme démarrée
        """
        self.status = 'processing'
        self.started_at = timezone.now()
        self.current_step = "Traitement en cours"
        self.progress_percentage = 10
        self.save(update_fields=['status', 'started_at', 'current_step', 'progress_percentage'])
    
    def mark_as_completed(self, colis=None):
        """
        Marque la tâche comme terminée avec succès
        """
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.current_step = "Terminé avec succès"
        self.progress_percentage = 100
        if colis:
            self.colis = colis
        self.save(update_fields=['status', 'completed_at', 'current_step', 'progress_percentage', 'colis'])
    
    def mark_as_failed(self, error_message):
        """
        Marque la tâche comme échouée
        """
        self.retry_count += 1
        self.error_message = error_message
        
        if self.can_retry():
            self.status = 'failed_retry'
            self.next_retry_at = timezone.now() + timezone.timedelta(minutes=5 * self.retry_count)
            self.current_step = f"Échec - retry {self.retry_count}/{self.max_retries} dans 5 min"
        else:
            self.status = 'failed_final'
            self.current_step = "Échec définitif"
            
        self.save(update_fields=[
            'status', 'error_message', 'retry_count', 
            'next_retry_at', 'current_step'
        ])
    
    def update_progress(self, step, percentage):
        """
        Met à jour la progression de la tâche
        """
        self.current_step = step
        self.progress_percentage = min(percentage, 100)
        self.save(update_fields=['current_step', 'progress_percentage'])
    
    def save(self, *args, **kwargs):
        """
        Génère automatiquement un task_id unique si non fourni
        """
        if not self.task_id:
            import uuid
            import time
            # Générer un ID unique avec timestamp pour éviter les collisions
            timestamp = str(int(time.time() * 1000))  # millisecondes
            unique_part = str(uuid.uuid4())[:8].upper()
            self.task_id = f"TASK_{timestamp}_{unique_part}"
            
            # Vérifier l'unicité (double sécurité)
            while ColisCreationTask.objects.filter(task_id=self.task_id).exists():
                unique_part = str(uuid.uuid4())[:8].upper()
                self.task_id = f"TASK_{timestamp}_{unique_part}"
                
        super().save(*args, **kwargs)
