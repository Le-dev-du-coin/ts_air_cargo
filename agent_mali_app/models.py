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
    Modèle pour enregistrer la réception des lots au Mali avec suivi des réceptions partielles
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
        verbose_name="Date de première réception"
    )
    
    date_derniere_maj = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière mise à jour"
    )
    
    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Historique des réceptions"
    )
    
    reception_complete = models.BooleanField(
        default=False,
        verbose_name="Réception complète"
    )
    
    colis_manquants = models.ManyToManyField(
        'agent_chine_app.Colis',
        blank=True,
        related_name='receptions_manquantes',
        verbose_name="Colis manquants"
    )
    
    frais_dedouanement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Frais de dédouanement (FCFA)",
        help_text="Frais de dédouanement pour le lot (en FCFA)"
    )
    
    nombre_colis_recus = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de colis reçus"
    )
    
    class Meta:
        verbose_name = "Réception de lot"
        verbose_name_plural = "Réceptions de lots"
        ordering = ['-date_derniere_maj']

    def __str__(self):
        status = "Complète" if self.reception_complete else "Partielle"
        return f"Réception {status} du lot {self.lot.numero_lot} - {self.date_derniere_maj.strftime('%d/%m/%Y %H:%M')}"
        
    def ajouter_observation(self, texte):
        """Ajoute une observation avec un horodatage"""
        horodatage = timezone.now().strftime('%d/%m/%Y %H:%M')
        if self.observations:
            self.observations += f"\n--- {horodatage} ---\n{texte}"
        else:
            self.observations = f"--- {horodatage} ---\n{texte}"

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


class PriceAdjustment(models.Model):
    """
    Modèle pour gérer les ajustements de prix (Jetons Cédés et Remises)
    """
    ADJUSTMENT_TYPES = [
        ('jc', 'Jeton Cédé (JC)'),
        ('remise', 'Remise Commerciale'),
        ('frais_supplementaire', 'Frais Supplémentaire'),
        ('correction', 'Correction de Prix'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('applied', 'Appliqué'),
        ('cancelled', 'Annulé'),
    ]
    
    # Référence au colis concerné
    colis = models.ForeignKey(
        'agent_chine_app.Colis',
        on_delete=models.CASCADE,
        related_name='price_adjustments',
        help_text="Colis concerné par l'ajustement"
    )
    
    # Type d'ajustement
    adjustment_type = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_TYPES,
        help_text="Type d'ajustement de prix"
    )
    
    # Montant de l'ajustement (toujours en valeur absolue)
    adjustment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Montant de l'ajustement en FCFA (valeur absolue)"
    )
    
    # Prix avant et après ajustement
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix original avant ajustement"
    )
    
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix final après ajustement"
    )
    
    # Informations contextuelles
    reason = models.CharField(
        max_length=200,
        help_text="Raison de l'ajustement"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes additionnelles sur l'ajustement"
    )
    
    # Statut et traçabilité
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_agent_mali': True},
        help_text="Agent Mali qui a appliqué l'ajustement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'application de l'ajustement"
    )
    
    class Meta:
        verbose_name = "Ajustement de Prix"
        verbose_name_plural = "Ajustements de Prix"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['colis', 'status']),
            models.Index(fields=['adjustment_type', 'created_at']),
            models.Index(fields=['applied_by', 'created_at']),
        ]
    
    def __str__(self):
        sign = "-" if self.adjustment_type in ['jc', 'remise'] else "+"
        return f"{self.get_adjustment_type_display()} - {self.colis.numero_suivi} ({sign}{self.adjustment_amount} FCFA)"
    
    def save(self, *args, **kwargs):
        """
        Calcul automatique du prix final
        """
        if self.adjustment_type in ['jc', 'remise']:
            # Déduction pour JC et remises
            self.final_price = self.original_price - self.adjustment_amount
        else:
            # Addition pour frais supplémentaires
            self.final_price = self.original_price + self.adjustment_amount
        
        # S'assurer que le prix final ne soit pas négatif
        if self.final_price < 0:
            self.final_price = 0
        
        super().save(*args, **kwargs)
    
    def apply_adjustment(self):
        """
        Marque l'ajustement comme appliqué et met à jour le prix du colis
        """
        if self.status != 'active':
            raise ValueError("Seuls les ajustements actifs peuvent être appliqués")
        
        # Mettre à jour le colis avec le nouveau prix
        self.colis.prix_transport_manuel = self.final_price
        self.colis.save()
        
        # Marquer comme appliqué
        self.status = 'applied'
        self.applied_at = timezone.now()
        self.save()
    
    def cancel_adjustment(self):
        """
        Annule l'ajustement et restaure le prix original
        """
        if self.status == 'applied':
            # Restaurer le prix original du colis
            self.colis.prix_transport_manuel = None  # Retour au prix calculé automatiquement
            self.colis.save()
        
        self.status = 'cancelled'
        self.save()
    
    @property
    def effective_adjustment(self):
        """
        Retourne le montant effectif de l'ajustement (négatif pour déduction)
        """
        if self.adjustment_type in ['jc', 'remise']:
            return -self.adjustment_amount
        return self.adjustment_amount
    
    @classmethod
    def create_jeton_cede(cls, colis, amount, reason="Change de monnaie", applied_by=None):
        """
        Méthode helper pour créer un ajustement de type Jeton Cédé
        """
        return cls.objects.create(
            colis=colis,
            adjustment_type='jc',
            adjustment_amount=abs(amount),  # S'assurer que c'est positif
            original_price=colis.get_prix_effectif(),
            reason=reason,
            applied_by=applied_by,
            notes=f"Jeton cédé de {amount} FCFA pour {reason}"
        )
    
    @classmethod
    def create_remise(cls, colis, amount, reason="Remise commerciale", applied_by=None):
        """
        Méthode helper pour créer une remise
        """
        return cls.objects.create(
            colis=colis,
            adjustment_type='remise',
            adjustment_amount=abs(amount),
            original_price=colis.get_prix_effectif(),
            reason=reason,
            applied_by=applied_by,
            notes=f"Remise de {amount} FCFA - {reason}"
        )
