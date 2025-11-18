from django.db import models
from django.conf import settings
from django.utils import timezone

class ShippingPrice(models.Model):
    """
    Modèle ShippingPrice selon les spécifications du DEVBOOK
    Gère les tarifs de transport avec les méthodes de calcul
    """
    METHODE_CALCUL_CHOICES = [
        ('par_kilo', 'Par Kilo'),
        ('par_metre_cube', 'Par Mètre Cube'),
        ('par_piece', 'Par Pièce'),
        ('forfaitaire', 'Prix Forfaitaire'),
        ('mixte', 'Mixte (Poids + Volume)'),
    ]
    
    TYPE_TRANSPORT_CHOICES = [
        ('cargo', 'Cargo'),
        ('express', 'Express'),
        ('bateau', 'Bateau'),
        ('all', 'Tous'),
    ]
    
    TYPE_COLIS_CHOICES = [
        ('standard', 'Standard'),
        ('telephone', 'Téléphone'),
        ('electronique', 'Électronique'),
        ('all', 'Tous types'),
    ]
    
    nom_tarif = models.CharField(
        max_length=100,
        help_text="Nom du tarif (ex: Tarif Standard, Tarif Express, etc.)"
    )
    
    methode_calcul = models.CharField(
        max_length=20,
        choices=METHODE_CALCUL_CHOICES,
        help_text="Méthode de calcul du prix"
    )
    
    prix_par_kilo = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix en FCFA par kilogramme"
    )
    
    prix_par_m3 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix en FCFA par mètre cube"
    )
    
    prix_forfaitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix forfaitaire en FCFA"
    )
    
    prix_par_piece = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Prix en FCFA par pièce (pour téléphones, électronique, etc.)"
    )
    
    type_transport = models.CharField(
        max_length=20,
        choices=TYPE_TRANSPORT_CHOICES,
        default='all',
        help_text="Type de transport concerné par ce tarif"
    )
    
    type_colis = models.CharField(
        max_length=20,
        choices=TYPE_COLIS_CHOICES,
        default='all',
        help_text="Type de colis concerné (pour tarif à la pièce)"
    )
    
    poids_minimum = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Poids minimum pour appliquer ce tarif (en kg)"
    )
    
    poids_maximum = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Poids maximum pour ce tarif (en kg, null = illimité)"
    )
    
    volume_minimum = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        default=0,
        help_text="Volume minimum pour ce tarif (en m3)"
    )
    
    volume_maximum = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Volume maximum pour ce tarif (en m3, null = illimité)"
    )
    
    actif = models.BooleanField(
        default=True,
        help_text="Tarif actif ou non"
    )
    
    date_debut = models.DateField(
        default=timezone.now,
        help_text="Date de début de validité du tarif"
    )
    
    date_fin = models.DateField(
        null=True,
        blank=True,
        help_text="Date de fin de validité (null = illimitée)"
    )
    
    pays_destination = models.CharField(
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
            ('ALL', 'Tous les pays'),
        ],
        default='ML',
        help_text="Pays de destination pour ce tarif"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description détaillée du tarif"
    )
    
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tarifs_crees'
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tarif de Transport"
        verbose_name_plural = "Tarifs de Transport"
        ordering = ['-date_creation']
        
    def __str__(self):
        return f"{self.nom_tarif} - {self.get_methode_calcul_display()} - {self.pays_destination}"
    
    def calculer_prix(self, poids_kg, volume_m3, quantite_pieces=1):
        """
        Calculer le prix selon la méthode définie
        Ajout du paramètre quantite_pieces pour tarif à la pièce
        """
        if not self.actif:
            return 0
        
        # Vérifier les limites de poids (sauf pour tarif à la pièce)
        if self.methode_calcul != 'par_piece':
            if poids_kg < self.poids_minimum:
                return 0
            if self.poids_maximum and poids_kg > self.poids_maximum:
                return 0
        
        # Vérifier les limites de volume (sauf pour tarif à la pièce)
        if self.methode_calcul != 'par_piece':
            if volume_m3 < self.volume_minimum:
                return 0
            if self.volume_maximum and volume_m3 > self.volume_maximum:
                return 0
        
        # Calcul selon la méthode
        if self.methode_calcul == 'par_kilo':
            return poids_kg * self.prix_par_kilo if self.prix_par_kilo else 0
        
        elif self.methode_calcul == 'par_metre_cube':
            return volume_m3 * self.prix_par_m3 if self.prix_par_m3 else 0
        
        elif self.methode_calcul == 'par_piece':
            return quantite_pieces * self.prix_par_piece if self.prix_par_piece else 0
        
        elif self.methode_calcul == 'forfaitaire':
            return self.prix_forfaitaire if self.prix_forfaitaire else 0
        
        elif self.methode_calcul == 'mixte':
            # Prendre le maximum entre le prix au poids et au volume
            prix_poids = poids_kg * self.prix_par_kilo if self.prix_par_kilo else 0
            prix_volume = volume_m3 * self.prix_par_m3 if self.prix_par_m3 else 0
            return max(prix_poids, prix_volume)
        
        return 0

class RapportOperationnel(models.Model):
    """
    Modèle pour stocker les rapports opérationnels générés
    """
    TYPE_RAPPORT_CHOICES = [
        ('journalier', 'Rapport Journalier'),
        ('hebdomadaire', 'Rapport Hebdomadaire'),
        ('mensuel', 'Rapport Mensuel'),
        ('financier', 'Rapport Financier'),
        ('synthese', 'Rapport de Synthèse'),
    ]
    
    titre = models.CharField(
        max_length=200,
        help_text="Titre du rapport"
    )
    
    type_rapport = models.CharField(
        max_length=20,
        choices=TYPE_RAPPORT_CHOICES
    )
    
    periode_debut = models.DateField(
        help_text="Début de la période couverte"
    )
    
    periode_fin = models.DateField(
        help_text="Fin de la période couverte"
    )
    
    contenu_json = models.JSONField(
        help_text="Contenu du rapport au format JSON"
    )
    
    fichier_pdf = models.FileField(
        upload_to='rapports/',
        null=True,
        blank=True,
        help_text="Fichier PDF du rapport"
    )
    
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rapports_generes'
    )
    
    envoye_admins = models.BooleanField(
        default=False,
        help_text="Rapport envoyé aux administrateurs"
    )
    
    date_generation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Rapport Opérationnel"
        verbose_name_plural = "Rapports Opérationnels"
        ordering = ['-date_generation']
        
    def __str__(self):
        return f"{self.titre} - {self.periode_debut} à {self.periode_fin}"
