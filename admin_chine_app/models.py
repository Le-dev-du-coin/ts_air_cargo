from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

class InventoryChina(models.Model):
    """
    Inventaire des produits et fournisseurs en Chine
    Gestion du stock et des approvisionnements
    """
    CATEGORY_CHOICES = [
        ('electronique', 'Électronique'),
        ('vetements', 'Vêtements'),
        ('maison', 'Maison & Jardin'),
        ('automobile', 'Automobile'),
        ('beaute', 'Beauté & Santé'),
        ('sport', 'Sport & Loisirs'),
        ('outils', 'Outils & Industrie'),
        ('autre', 'Autre'),
    ]
    
    STATUS_CHOICES = [
        ('actif', 'Actif'),
        ('rupture', 'En rupture'),
        ('commande', 'En commande'),
        ('discontinu', 'Discontinué'),
    ]
    
    nom_produit = models.CharField(
        max_length=200,
        help_text="Nom du produit ou article"
    )
    
    code_produit = models.CharField(
        max_length=50,
        unique=True,
        help_text="Code unique du produit"
    )
    
    categorie = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='autre'
    )
    
    fournisseur_nom = models.CharField(
        max_length=200,
        help_text="Nom du fournisseur chinois"
    )
    
    fournisseur_contact = models.CharField(
        max_length=100,
        blank=True,
        help_text="Contact du fournisseur (WeChat, Téléphone)"
    )
    
    prix_unitaire_yuan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix d'achat en Yuan chinois"
    )
    
    prix_unitaire_fcfa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix équivalent en FCFA (calculé automatiquement)"
    )
    
    taux_change_utilise = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Taux de change Yuan/FCFA utilisé"
    )
    
    quantite_stock = models.PositiveIntegerField(
        default=0,
        help_text="Quantité en stock"
    )
    
    quantite_minimale = models.PositiveIntegerField(
        default=10,
        help_text="Seuil d'alerte stock minimum"
    )
    
    poids_unitaire = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Poids unitaire en kg"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='actif'
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description détaillée du produit"
    )
    
    image_produit = models.ImageField(
        upload_to='inventory_china/',
        null=True,
        blank=True,
        help_text="Photo du produit"
    )
    
    admin_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'is_admin_chine': True},
        related_name='inventaires_crees'
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inventaire Chine"
        verbose_name_plural = "Inventaires Chine"
        ordering = ['-date_modification']
    
    def save(self, *args, **kwargs):
        # Calcul automatique du prix en FCFA si taux de change fourni
        if self.prix_unitaire_yuan and self.taux_change_utilise:
            self.prix_unitaire_fcfa = self.prix_unitaire_yuan * self.taux_change_utilise
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom_produit} ({self.code_produit}) - {self.quantite_stock} en stock"
    
    @property
    def is_low_stock(self):
        """Retourne True si le stock est en dessous du seuil minimum"""
        return self.quantite_stock <= self.quantite_minimale
    
    @property
    def valeur_stock_yuan(self):
        """Valeur totale du stock en Yuan"""
        return self.quantite_stock * self.prix_unitaire_yuan
    
    @property
    def valeur_stock_fcfa(self):
        """Valeur totale du stock en FCFA"""
        if self.prix_unitaire_fcfa:
            return self.quantite_stock * self.prix_unitaire_fcfa
        return 0


class OperationChina(models.Model):
    """
    Suivi des opérations spécifiques côté Chine
    Achats, mouvements de stock, expéditions
    """
    TYPE_OPERATION_CHOICES = [
        ('achat', 'Achat produit'),
        ('vente', 'Vente produit'),
        ('entree_stock', 'Entrée en stock'),
        ('sortie_stock', 'Sortie de stock'),
        ('expedition', 'Expédition vers Mali'),
        ('retour', 'Retour/Échange'),
        ('inventaire', 'Correction inventaire'),
    ]
    
    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ]
    
    numero_operation = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Numéro auto-généré: OP + date + compteur"
    )
    
    type_operation = models.CharField(
        max_length=20,
        choices=TYPE_OPERATION_CHOICES
    )
    
    produit = models.ForeignKey(
        InventoryChina,
        on_delete=models.CASCADE,
        related_name='operations',
        null=True,
        blank=True
    )
    
    quantite = models.PositiveIntegerField(
        help_text="Quantité concernée par l'opération"
    )
    
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix unitaire de l'opération"
    )
    
    montant_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Montant total de l'opération"
    )
    
    monnaie = models.CharField(
        max_length=10,
        choices=[
            ('CNY', 'Yuan Chinois'),
            ('USD', 'Dollar US'),
            ('XOF', 'FCFA'),
        ],
        default='CNY'
    )
    
    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='en_attente'
    )
    
    description = models.TextField(
        help_text="Description de l'opération"
    )
    
    fournisseur_contact = models.CharField(
        max_length=200,
        blank=True,
        help_text="Contact du fournisseur/client"
    )
    
    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence externe (bon de commande, facture, etc.)"
    )
    
    admin_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_admin_chine': True},
        related_name='operations_gerees'
    )
    
    date_operation = models.DateTimeField(
        help_text="Date effective de l'opération"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Opération Chine"
        verbose_name_plural = "Opérations Chine"
        ordering = ['-date_operation']
    
    def save(self, *args, **kwargs):
        if not self.numero_operation:
            # Générer numéro d'opération: OP + date + compteur
            today = timezone.now()
            date_str = today.strftime('%Y%m%d')
            count = OperationChina.objects.filter(
                numero_operation__startswith=f'OP{date_str}'
            ).count() + 1
            self.numero_operation = f"OP{date_str}{count:04d}"
        
        # Calculer montant total si prix unitaire fourni
        if self.prix_unitaire and self.quantite:
            self.montant_total = self.prix_unitaire * self.quantite
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.numero_operation} - {self.type_operation} - {self.statut}"
