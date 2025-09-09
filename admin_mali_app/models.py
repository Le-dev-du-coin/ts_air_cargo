from django.db import models
from django.conf import settings
from django.utils import timezone

class TransfertArgent(models.Model):
    """
    Modèle TransfertArgent selon les spécifications du DEVBOOK
    Gère les transferts d'argent du Mali vers la Chine
    """
    STATUS_CHOICES = [
        ('initie', 'Initié'),
        ('envoye', 'Envoyé'),
        ('confirme_chine', 'Confirmé en Chine'),
        ('annule', 'Annulé'),
    ]
    
    METHODE_CHOICES = [
        ('virement_bancaire', 'Virement bancaire'),
        ('western_union', 'Western Union'),
        ('moneygram', 'MoneyGram'),
        ('orange_money', 'Orange Money'),
        ('moov_money', 'Moov Money'),
        ('autre', 'Autre'),
    ]
    
    numero_transfert = models.CharField(
        max_length=20,
        unique=True,
        help_text="Numéro unique du transfert"
    )
    
    montant_fcfa = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Montant en FCFA"
    )
    
    montant_yuan = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Montant équivalent en Yuan chinois"
    )
    
    taux_change = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Taux de change FCFA/Yuan utilisé"
    )
    
    methode_transfert = models.CharField(
        max_length=30,
        choices=METHODE_CHOICES,
        help_text="Méthode utilisée pour le transfert"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='initie'
    )
    
    admin_mali = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_admin_mali': True},
        related_name='transferts_inities',
        help_text="Administrateur Mali qui a initié le transfert"
    )
    
    admin_chine = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'is_admin_chine': True},
        related_name='transferts_confirmes',
        help_text="Administrateur Chine qui a confirmé la réception"
    )
    
    date_initiation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'initiation du transfert"
    )
    
    date_envoi = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date effective d'envoi"
    )
    
    date_confirmation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de confirmation de réception en Chine"
    )
    
    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence du service de transfert (Western Union, etc.)"
    )
    
    destinataire_nom = models.CharField(
        max_length=200,
        help_text="Nom du destinataire en Chine"
    )
    
    destinataire_telephone = models.CharField(
        max_length=20,
        help_text="Téléphone du destinataire en Chine"
    )
    
    destinataire_adresse = models.TextField(
        help_text="Adresse du destinataire en Chine"
    )
    
    motif_transfert = models.TextField(
        help_text="Motif du transfert d'argent"
    )
    
    frais_transfert = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Frais de transfert en FCFA"
    )
    
    justificatifs = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste des documents justificatifs"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes additionnelles sur le transfert"
    )
    
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Transfert d'Argent"
        verbose_name_plural = "Transferts d'Argent"
        ordering = ['-date_initiation']
        
    def save(self, *args, **kwargs):
        if not self.numero_transfert:
            # Générer numéro de transfert: TM + année + mois + compteur
            today = timezone.now()
            date_str = today.strftime('%Y%m')
            count = TransfertArgent.objects.filter(
                numero_transfert__startswith=f'TM{date_str}'
            ).count() + 1
            self.numero_transfert = f"TM{date_str}{count:04d}"
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Transfert {self.numero_transfert} - {self.montant_fcfa} FCFA - {self.statut}"
    
    @property
    def montant_net_fcfa(self):
        """
        Montant net après déduction des frais
        """
        return self.montant_fcfa - self.frais_transfert
