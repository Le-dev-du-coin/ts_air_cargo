from django.db import models
from django.conf import settings
from django.utils import timezone
from ts_air_cargo.validators import validate_justificatif_file, validate_signature_file, validate_filename_security

class Depense(models.Model):
    """
    Modèle Depense selon les spécifications du DEVBOOK
    Permet aux agents au Mali d'enregistrer leurs dépenses opérationnelles
    """
    TYPE_DEPENSE_CHOICES = [
        ('transport', 'Transport'),
        ('manutention', 'Manutention'),
        ('douane', 'Frais de douane'),
        ('stockage', 'Stockage'),
        ('carburant', 'Carburant'),
        ('reparation', 'Réparation'),
        ('communication', 'Communication'),
        ('bureau', 'Frais de bureau'),
        ('autre', 'Autre'),
    ]
    
    libelle = models.CharField(
        max_length=200,
        help_text="Description de la dépense"
    )
    
    type_depense = models.CharField(
        max_length=20,
        choices=TYPE_DEPENSE_CHOICES,
        help_text="Catégorie de la dépense"
    )
    
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Montant en FCFA"
    )
    
    date_depense = models.DateField(
        default=timezone.now,
        help_text="Date de la dépense"
    )
    
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_agent_mali': True},
        related_name='depenses',
        help_text="Agent qui a effectué la dépense"
    )
    
    justificatif = models.FileField(
        upload_to='depenses/justificatifs/',
        null=True,
        blank=True,
        validators=[validate_justificatif_file, validate_filename_security],
        help_text="Pièce justificative (facture, reçu, etc.) - Max 15MB"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes additionnelles sur la dépense"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_depense', '-date_creation']
        
    def __str__(self):
        return f"{self.libelle} - {self.montant} FCFA ({self.date_depense})"

class ReceptionLot(models.Model):
    """
    Modèle pour enregistrer la réception des lots au Mali
    """
    lot = models.OneToOneField(
        'agent_chine_app.Lot',
        on_delete=models.CASCADE,
        related_name='reception_mali'
    )
    
    agent_receptionnaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_agent_mali': True},
        related_name='lots_receptionnes'
    )
    
    date_reception = models.DateTimeField(
        default=timezone.now,
        help_text="Date et heure de réception du lot"
    )
    
    reception_complete = models.BooleanField(
        default=True,
        help_text="Le lot est-il reçu en totalité?"
    )
    
    colis_manquants = models.ManyToManyField(
        'agent_chine_app.Colis',
        blank=True,
        help_text="Colis manquants lors de la réception"
    )
    
    colis_endommages = models.ManyToManyField(
        'agent_chine_app.Colis',
        blank=True,
        related_name='endommagements',
        help_text="Colis endommagés lors de la réception"
    )
    
    observations = models.TextField(
        blank=True,
        help_text="Observations sur l'état du lot reçu"
    )
    
    class Meta:
        verbose_name = "Réception de Lot"
        verbose_name_plural = "Réceptions de Lots"
        ordering = ['-date_reception']
        
    def __str__(self):
        return f"Réception {self.lot.numero_lot} - {self.date_reception.strftime('%d/%m/%Y')}"

class Livraison(models.Model):
    """
    Modèle pour gérer les livraisons de colis aux clients
    """
    STATUS_CHOICES = [
        ('planifiee', 'Planifiée'),
        ('en_cours', 'En cours'),
        ('livree', 'Livrée'),
        ('echec', 'Échec'),
        ('reprogrammee', 'Reprogrammée'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('paye', 'Payé'),
        ('en_attente', 'En attente de paiement'),
    ]
    
    colis = models.ForeignKey(
        'agent_chine_app.Colis',
        on_delete=models.CASCADE,
        related_name='livraisons'
    )
    
    agent_livreur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_agent_mali': True},
        related_name='livraisons_effectuees'
    )
    
    date_planifiee = models.DateTimeField(
        help_text="Date et heure prévues pour la livraison"
    )
    
    date_livraison_effective = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure effectives de livraison"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planifiee'
    )
    
    adresse_livraison = models.TextField(
        help_text="Adresse de livraison du colis"
    )
    
    telephone_destinataire = models.CharField(
        max_length=15,
        help_text="Téléphone du destinataire"
    )
    
    nom_destinataire = models.CharField(
        max_length=200,
        help_text="Nom de la personne qui a reçu le colis"
    )
    
    signature_destinataire = models.FileField(
        upload_to='livraisons/signatures/',
        null=True,
        blank=True,
        validators=[validate_signature_file, validate_filename_security],
        help_text="Signature du destinataire - Max 2MB, formats: JPG, PNG"
    )
    
    notes_livraison = models.TextField(
        blank=True,
        help_text="Notes sur la livraison"
    )
    
    montant_collecte = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Montant collecté lors de la livraison (si paiement au Mali)"
    )
    
    statut_paiement = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='en_attente',
        help_text="Statut du paiement du transport"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Livraison"
        verbose_name_plural = "Livraisons"
        ordering = ['-date_planifiee']
        
    def __str__(self):
        return f"Livraison {self.colis.numero_suivi} - {self.statut}"
