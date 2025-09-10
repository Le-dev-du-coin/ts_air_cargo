from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

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
    
    numero_lot = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Numéro auto-généré: date + chiffres"
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
            # Générer numéro de lot: date + chiffres
            date_str = timezone.now().strftime('%Y%m%d')
            count = Lot.objects.filter(
                numero_lot__startswith=date_str
            ).count() + 1
            self.numero_lot = f"{date_str}{count:03d}"
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
        help_text="Photo du colis"
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
                    multiplier = 600 if self.type_transport == 'express' else 500
                    prix_max = float(self.poids) * multiplier
                else:  # bateau
                    # Prix basé sur le volume
                    prix_max = volume_m3 * 50000  # 50 000 CFA par m³
                    
            return max(prix_max, 1000)  # Prix minimum de 1000 CFA
            
        except Exception as e:
            # En cas d'erreur, retourner un prix basique
            if self.type_transport in ['cargo', 'express']:
                return float(self.poids) * 500
            else:
                return self.volume_m3() * 50000
