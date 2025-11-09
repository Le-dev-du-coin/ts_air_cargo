"""
Constantes réutilisables pour l'application Agent Chine
"""

# Choix de statuts pour les colis
COLIS_STATUS_CHOICES = [
    ('en_attente', 'En Attente'),
    ('receptionne_chine', 'Réceptionné en Chine'),
    ('en_transit', 'En Transit'),
    ('arrive', 'Arrivé au Mali'),
    ('livre', 'Livré'),
    ('perdu', 'Perdu'),
]

# Choix de modes de paiement pour les colis
COLIS_PAYMENT_CHOICES = [
    ('paye_chine', 'Payé en Chine'),
    ('paye_mali', 'Payé au Mali'),
    ('non_paye', 'Non Payé'),
]

# Choix de types de transport
TRANSPORT_CHOICES = [
    ('cargo', 'Cargo'),
    ('express', 'Express'),
    ('bateau', 'Bateau'),
]

# Choix de statuts pour les lots
LOT_STATUS_CHOICES = [
    ('ouvert', 'Ouvert'),
    ('ferme', 'Fermé'),
    ('expedie', 'Expédié'),
    ('en_transit', 'En Transit'),
    ('arrive', 'Arrivé au Mali'),
    ('livre', 'Livré'),
]

# Choix de pays pour les clients
PAYS_CHOICES = [
    ('ML', 'Mali'),
    ('SN', 'Sénégal'),
    ('CI', "Côte d'Ivoire"),
    ('BF', 'Burkina Faso'),
    ('NE', 'Niger'),
    ('GN', 'Guinée'),
    ('MR', 'Mauritanie'),
    ('GM', 'Gambie'),
    ('GW', 'Guinée-Bissau'),
]

# Tarifs par défaut (en FCFA)
DEFAULT_PRICES = {
    'cargo': 10000,  # FCFA par kg
    'express': 12000,  # FCFA par kg
    'bateau': 300000,  # FCFA par m³
}

# Prix minimum pour un colis (en FCFA)
MIN_COLIS_PRICE = 1000
