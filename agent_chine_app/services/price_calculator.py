"""
Service de calcul de prix pour les colis
Centralise toute la logique de calcul de prix
"""
from decimal import Decimal
from typing import Dict, Optional
from ..constants import DEFAULT_PRICES, MIN_COLIS_PRICE


class PriceCalculator:
    """
    Service pour calculer les prix des colis selon différentes méthodes
    """
    
    @staticmethod
    def calculate_volume_m3(longueur: float, largeur: float, hauteur: float) -> float:
        """
        Calcule le volume en mètres cubes
        
        Args:
            longueur: Longueur en cm
            largeur: Largeur en cm
            hauteur: Hauteur en cm
            
        Returns:
            Volume en m³
        """
        return (longueur * largeur * hauteur) / 1000000
    
    @staticmethod
    def calculate_default_price(
        poids: float,
        volume_m3: float,
        type_transport: str
    ) -> float:
        """
        Calcule le prix par défaut selon le type de transport
        
        Args:
            poids: Poids en kg
            volume_m3: Volume en m³
            type_transport: Type de transport (cargo, express, bateau)
            
        Returns:
            Prix calculé en FCFA
        """
        if type_transport == 'bateau':
            prix = volume_m3 * DEFAULT_PRICES['bateau']
        else:
            prix = poids * DEFAULT_PRICES.get(type_transport, DEFAULT_PRICES['cargo'])
        
        return max(prix, MIN_COLIS_PRICE)
    
    @staticmethod
    def calculate_price_with_tariff(
        poids: float,
        volume_m3: float,
        type_transport: str,
        pays_destination: str,
        tarifs_queryset
    ) -> Dict[str, any]:
        """
        Calcule le prix en utilisant les tarifs configurés
        
        Args:
            poids: Poids en kg
            volume_m3: Volume en m³
            type_transport: Type de transport
            pays_destination: Code du pays de destination
            tarifs_queryset: QuerySet des tarifs disponibles
            
        Returns:
            Dict avec prix, tarif_utilisé, et détails
        """
        # Filtrer les tarifs applicables
        tarifs = tarifs_queryset.filter(
            actif=True,
            pays_destination__in=[pays_destination, 'ALL']
        )
        
        prix_max = 0
        tarif_utilise = None
        prix_details = []
        
        # Calculer le prix avec chaque tarif
        for tarif in tarifs:
            try:
                prix_calcule = tarif.calculer_prix(poids, volume_m3)
                
                # Ajustement pour bateau (généralement moins cher)
                if type_transport == 'bateau':
                    prix_calcule *= 0.8
                
                prix_details.append({
                    'nom_tarif': tarif.nom_tarif,
                    'methode': tarif.methode_calcul,
                    'prix_calcule': float(prix_calcule)
                })
                
                if prix_calcule > prix_max:
                    prix_max = prix_calcule
                    tarif_utilise = tarif
                    
            except Exception as e:
                continue
        
        # Si aucun tarif applicable, utiliser le prix par défaut
        if prix_max == 0:
            prix_max = PriceCalculator.calculate_default_price(
                poids, volume_m3, type_transport
            )
            methode = 'tarif_defaut'
        else:
            methode = tarif_utilise.nom_tarif if tarif_utilise else 'inconnu'
        
        return {
            'prix': float(prix_max),
            'tarif_utilise': tarif_utilise,
            'methode': methode,
            'details': prix_details
        }
    
    @staticmethod
    def get_prix_effectif(
        prix_calcule: Decimal,
        prix_transport_manuel: Optional[Decimal]
    ) -> float:
        """
        Retourne le prix effectif (manuel prioritaire sur calculé)
        
        Args:
            prix_calcule: Prix calculé automatiquement
            prix_transport_manuel: Prix manuel (optionnel)
            
        Returns:
            Prix effectif à utiliser
        """
        if prix_transport_manuel and prix_transport_manuel > 0:
            return float(prix_transport_manuel)
        return float(prix_calcule)
    
    @staticmethod
    def get_source_prix(prix_transport_manuel: Optional[Decimal]) -> str:
        """
        Retourne la source du prix utilisé
        
        Args:
            prix_transport_manuel: Prix manuel (optionnel)
            
        Returns:
            'manuel' ou 'automatique'
        """
        if prix_transport_manuel and prix_transport_manuel > 0:
            return 'manuel'
        return 'automatique'
