"""
Modèles pour gérer les ajustements de prix dans l'agent Mali
- Jetons Cédés (JC) : Déductions pour change de monnaie
- Remises : Réductions commerciales sur le transport
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class PriceAdjustment(models.Model):
    """
    Modèle pour gérer tous types d'ajustements de prix
    """
    ADJUSTMENT_TYPES = [
        ('jc', 'Jeton Cédé (JC)'),
        ('remise', 'Remise Commerciale'),
        ('frais_supplementaire', 'Frais Supplémentaire'),
        ('correction', 'Correction de Prix'),
    ]
    
    CALCULATION_METHODS = [
        ('fixed', 'Montant Fixe'),
        ('percentage', 'Pourcentage'),
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
    
    # Calcul de l'ajustement
    calculation_method = models.CharField(
        max_length=20,
        choices=CALCULATION_METHODS,
        default='fixed',
        help_text="Méthode de calcul de l'ajustement"
    )
    
    # Valeurs pour le calcul
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Montant fixe en FCFA (si méthode fixe)"
    )
    
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Pourcentage de réduction/augmentation (si méthode pourcentage)"
    )
    
    # Prix avant et après ajustement
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix original avant ajustement"
    )
    
    adjusted_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Montant de l'ajustement (négatif pour déduction, positif pour ajout)"
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
    
    # Approbation (optionnel pour des seuils)
    requires_approval = models.BooleanField(
        default=False,
        help_text="Cet ajustement nécessite-t-il une approbation?"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_adjustments',
        help_text="Superviseur qui a approuvé l'ajustement"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'approbation"
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
        sign = "+" if self.adjusted_amount >= 0 else ""
        return f"{self.get_adjustment_type_display()} - {self.colis.numero_suivi} ({sign}{self.adjusted_amount} FCFA)"
    
    def save(self, *args, **kwargs):
        """
        Calcul automatique du montant d'ajustement et prix final
        """
        if self.calculation_method == 'fixed' and self.fixed_amount:
            self.adjusted_amount = -abs(self.fixed_amount) if self.adjustment_type in ['jc', 'remise'] else self.fixed_amount
        elif self.calculation_method == 'percentage' and self.percentage:
            percentage_amount = (self.original_price * self.percentage) / 100
            self.adjusted_amount = -percentage_amount if self.adjustment_type in ['jc', 'remise'] else percentage_amount
        
        self.final_price = self.original_price + self.adjusted_amount
        
        # S'assurer que le prix final ne soit pas négatif
        if self.final_price < 0:
            self.final_price = Decimal('0.00')
        
        super().save(*args, **kwargs)
    
    def apply_adjustment(self, applied_by=None):
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
        if applied_by:
            self.applied_by = applied_by
        
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
    
    @classmethod
    def create_jeton_cede(cls, colis, amount, reason="Change de monnaie", applied_by=None):
        """
        Méthode helper pour créer un ajustement de type Jeton Cédé
        """
        return cls.objects.create(
            colis=colis,
            adjustment_type='jc',
            calculation_method='fixed',
            fixed_amount=abs(amount),  # S'assurer que c'est positif
            original_price=colis.get_prix_effectif(),
            reason=reason,
            applied_by=applied_by,
            notes=f"Jeton cédé de {amount} FCFA pour {reason}"
        )
    
    @classmethod
    def create_remise(cls, colis, amount_or_percentage, is_percentage=False, reason="Remise commerciale", applied_by=None):
        """
        Méthode helper pour créer une remise
        """
        if is_percentage:
            return cls.objects.create(
                colis=colis,
                adjustment_type='remise',
                calculation_method='percentage',
                percentage=amount_or_percentage,
                original_price=colis.get_prix_effectif(),
                reason=reason,
                applied_by=applied_by,
                notes=f"Remise de {amount_or_percentage}% - {reason}"
            )
        else:
            return cls.objects.create(
                colis=colis,
                adjustment_type='remise',
                calculation_method='fixed',
                fixed_amount=amount_or_percentage,
                original_price=colis.get_prix_effectif(),
                reason=reason,
                applied_by=applied_by,
                notes=f"Remise de {amount_or_percentage} FCFA - {reason}"
            )


class PriceAdjustmentTemplate(models.Model):
    """
    Templates pré-configurés pour les ajustements fréquents
    """
    name = models.CharField(
        max_length=100,
        help_text="Nom du template"
    )
    
    adjustment_type = models.CharField(
        max_length=20,
        choices=PriceAdjustment.ADJUSTMENT_TYPES
    )
    
    calculation_method = models.CharField(
        max_length=20,
        choices=PriceAdjustment.CALCULATION_METHODS
    )
    
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    default_reason = models.CharField(
        max_length=200,
        help_text="Raison par défaut pour ce template"
    )
    
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    
    class Meta:
        verbose_name = "Template d'Ajustement"
        verbose_name_plural = "Templates d'Ajustements"
        ordering = ['name']
    
    def __str__(self):
        return self.name