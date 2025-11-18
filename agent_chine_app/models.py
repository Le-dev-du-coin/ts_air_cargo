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
    benefice = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        help_text="Bénéfice calculé (prix transport + frais douane - total colis)"
    )
    
    agent_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lots_crees'
    )
    
    class Meta:
        verbose_name_plural = "Lots"
        ordering = ['-date_creation']
        
    def save(self, *args, **kwargs):
        if not self.numero_lot:
            # Générer le numéro de lot si c'est une nouvelle instance
            prefix = self.type_lot.upper()
            today = timezone.now().strftime('%Y%m%d')
            
            # Trouver le prochain numéro de séquence
            last_lot = Lot.objects.filter(
                numero_lot__startswith=f"{prefix}-{today}"
            ).order_by('-numero_lot').first()
            
            if last_lot:
                try:
                    seq = int(last_lot.numero_lot.split('-')[-1]) + 1
                except (IndexError, ValueError):
                    seq = 1
            else:
                seq = 1
                
            self.numero_lot = f"{prefix}-{today}-{seq:03d}"
        
        # Calculer le bénéfice si le prix de transport est défini
        # Les frais de douane peuvent être None (seront traités comme 0)
        if self.prix_transport is not None:
            total_colis = sum(float(colis.get_prix_effectif()) for colis in self.colis.all())
            frais_douane = float(self.frais_douane) if self.frais_douane is not None else 0.0
            # Bénéfice = Revenus (prix colis) - Coûts (transport + douane)
            self.benefice = total_colis - (float(self.prix_transport) + frais_douane)
        else:
            self.benefice = None
            
        super().save(*args, **kwargs)
        
    def recalculer_benefice(self):
        """
        Recalcule le bénéfice et sauvegarde le lot
        Utile après mise à jour des frais de douane par l'agent Mali
        """
        if self.prix_transport is not None:
            total_colis = sum(float(colis.get_prix_effectif()) for colis in self.colis.all())
            frais_douane = float(self.frais_douane) if self.frais_douane is not None else 0.0
            # Bénéfice = Revenus (prix colis) - Coûts (transport + douane)
            self.benefice = total_colis - (float(self.prix_transport) + frais_douane)
            self.save(update_fields=['benefice'])
            return True
        return False
    
    def get_benefice_percentage(self):
        """
        Calcule le pourcentage de marge bénéficiaire par rapport au coût total
        """
        if self.benefice is None or not self.prix_transport:
            return 0.0
            
        total_cout = sum(float(colis.get_prix_effectif()) for colis in self.colis.all())
        if total_cout == 0:
            return 0.0
            
        return float((float(self.benefice) / total_cout) * 100)
        
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
    
    TYPE_COLIS_CHOICES = [
        ('standard', 'Standard (au kilo)'),
        ('telephone', 'Téléphone (à la pièce)'),
        ('electronique', 'Électronique (à la pièce)'),
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
    
    # Type de colis (pour tarification)
    type_colis = models.CharField(
        max_length=20,
        choices=TYPE_COLIS_CHOICES,
        default='standard',
        help_text="Type de tarification : Standard (au kilo) ou à la pièce"
    )
    
    # Quantité de pièces (pour téléphones/électronique)
    quantite_pieces = models.PositiveIntegerField(
        default=1,
        help_text="Nombre de pièces (pour téléphones/électronique)"
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
    
    prix_transport_manuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix de transport manuel défini par l'agent (prioritaire sur le calcul automatique)"
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
            
        # Calculer le prix automatiquement (toujours)
        self.prix_calcule = self.calculer_prix_automatique()
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.numero_suivi} - {self.client}"
    
    def volume_m3(self):
        """
        Calculer le volume en mètres cubes
        """
        return (self.longueur * self.largeur * self.hauteur) / 1000000  # cm3 vers m3
    
    def get_prix_effectif(self):
        """
        Retourne le prix effectif utilisé (manuel ou calculé)
        """
        if self.prix_transport_manuel and self.prix_transport_manuel > 0:
            return float(self.prix_transport_manuel)
        return float(self.prix_calcule)
    
    def get_source_prix(self):
        """
        Retourne la source du prix utilisé
        """
        if self.prix_transport_manuel and self.prix_transport_manuel > 0:
            return 'manuel'
        return 'automatique'
    
    def calculer_prix_automatique(self):
        """
        Calculer le prix automatiquement selon les tarifs configurés
        Support : Poids (Cargo/Express), Volume (Bateau), Pièce (Téléphone/Électronique)
        """
        try:
            from reporting_app.models import ShippingPrice
            
            volume_m3 = self.volume_m3()
            
            # PRIORITÉ 1 : Tarif à la pièce (téléphone/électronique)
            if self.type_transport in ['cargo', 'express'] and self.type_colis != 'standard':
                # Chercher tarif spécifique pour ce type de colis
                tarif_piece = ShippingPrice.objects.filter(
                    actif=True,
                    methode_calcul='par_piece',
                    type_transport__in=[self.type_transport, 'all'],
                    type_colis__in=[self.type_colis, 'all'],
                    pays_destination__in=[self.client.pays, 'ALL']
                ).first()
                
                if tarif_piece and tarif_piece.prix_par_piece:
                    prix = float(tarif_piece.prix_par_piece) * self.quantite_pieces
                    return max(prix, 1000)  # Minimum 1000 FCFA
            
            # PRIORITÉ 2 : Tarif au kilo (standard)
            if self.type_transport in ['cargo', 'express']:
                tarifs = ShippingPrice.objects.filter(
                    actif=True,
                    methode_calcul='par_kilo',
                    type_transport__in=[self.type_transport, 'all'],
                    pays_destination__in=[self.client.pays, 'ALL']
                )
                
                prix_max = 0
                for tarif in tarifs:
                    prix_calcule = tarif.calculer_prix(float(self.poids), volume_m3)
                    if prix_calcule > prix_max:
                        prix_max = prix_calcule
                
                if prix_max > 0:
                    return max(prix_max, 1000)
                
                # Prix par défaut si aucun tarif
                multiplier = 12000 if self.type_transport == 'express' else 10000
                return float(self.poids) * multiplier
            
            # PRIORITÉ 3 : Tarif au volume (bateau)
            else:  # bateau
                tarifs = ShippingPrice.objects.filter(
                    actif=True,
                    methode_calcul='par_metre_cube',
                    type_transport__in=['bateau', 'all'],
                    pays_destination__in=[self.client.pays, 'ALL']
                )
                
                prix_max = 0
                for tarif in tarifs:
                    prix_calcule = tarif.calculer_prix(float(self.poids), volume_m3)
                    if prix_calcule > prix_max:
                        prix_max = prix_calcule
                
                if prix_max > 0:
                    return max(prix_max, 1000)
                
                # Prix par défaut
                return volume_m3 * 300000
            
        except Exception as e:
            # Fallback en cas d'erreur
            if self.type_transport in ['cargo', 'express']:
                if self.type_colis == 'telephone':
                    return 5000 * self.quantite_pieces
                elif self.type_colis == 'electronique':
                    return 3000 * self.quantite_pieces
                else:
                    return float(self.poids) * 10000
            else:
                return self.volume_m3() * 300000


class ClientCreationTask(models.Model):
    """
    Tâche de création de client avec notifications WhatsApp
    Permet de tracker l'état des notifications lors de la création de clients
    """
    TASK_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('account_creating', 'Création compte...'),
        ('notification_sending', 'Envoi notifications...'),
        ('completed', 'Terminé'),
        ('failed', 'Échec'),
        ('failed_retry', 'Échec - retry programmé'),
        ('failed_final', 'Échec définitif'),
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
    
    # Données client
    telephone = models.CharField(
        max_length=20,
        help_text="Numéro de téléphone du client"
    )
    first_name = models.CharField(
        max_length=100,
        help_text="Prénom du client"
    )
    last_name = models.CharField(
        max_length=100,
        help_text="Nom du client"
    )
    email = models.EmailField(
        blank=True,
        help_text="Email du client"
    )
    
    # Relations
    client = models.ForeignKey(
        'Client',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Client créé (null pendant le traitement)"
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text="Agent qui a initié la tâche"
    )
    
    # Résultat des notifications
    notifications_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Données des notifications envoyées"
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
        verbose_name = "Tâche de Création Client"
        verbose_name_plural = "Tâches de Création Client"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['initiated_by', 'status']),
            models.Index(fields=['telephone', 'status']),
        ]
        
    def __str__(self):
        return f"Client {self.telephone} - {self.get_status_display()}"
    
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
    
    def mark_as_started(self):
        """
        Marque la tâche comme démarrée
        """
        self.status = 'processing'
        self.started_at = timezone.now()
        self.current_step = "Traitement en cours"
        self.progress_percentage = 10
        self.save(update_fields=['status', 'started_at', 'current_step', 'progress_percentage'])
    
    def mark_as_completed(self, client=None, notifications_data=None):
        """
        Marque la tâche comme terminée avec succès
        """
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.current_step = "Notifications envoyées avec succès"
        self.progress_percentage = 100
        if client:
            self.client = client
        if notifications_data:
            self.notifications_data = notifications_data
        self.save(update_fields=[
            'status', 'completed_at', 'current_step', 'progress_percentage', 
            'client', 'notifications_data'
        ])
    
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
            self.current_step = "Échec définitif des notifications"
            
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
            # Générer un ID unique avec timestamp
            timestamp = str(int(time.time() * 1000))
            unique_part = str(uuid.uuid4())[:8].upper()
            self.task_id = f"CLIENT_{timestamp}_{unique_part}"
            
            # Vérifier l'unicité
            while ClientCreationTask.objects.filter(task_id=self.task_id).exists():
                unique_part = str(uuid.uuid4())[:8].upper()
                self.task_id = f"CLIENT_{timestamp}_{unique_part}"
                
        super().save(*args, **kwargs)


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
        null=True,
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
