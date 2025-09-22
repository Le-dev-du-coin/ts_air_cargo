"""
Script pour patcher le service WaChap avec la gestion améliorée des timeouts
"""

import re

def patch_wachap_service():
    """
    Applique les améliorations de gestion de timeout au service WaChap
    """
    
    # Lire le fichier original
    with open('/var/www/ts_air_cargo/notifications_app/wachap_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ajouter l'import du timeout handler au début du fichier
    imports_section = '''"""
Service WaChap pour l'envoi de messages WhatsApp
Support double instance : Chine et Mali
Migration Twilio → WaChap pour TS Air Cargo
"""

import requests
import logging
import json
import re
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.core.cache import cache
from urllib.parse import quote
from django.utils import timezone
from .timeout_handler import timeout_handler, circuit_breaker'''
    
    # Remplacer la section imports
    old_imports = '''"""
Service WaChap pour l'envoi de messages WhatsApp
Support double instance : Chine et Mali
Migration Twilio → WaChap pour TS Air Cargo
"""

import requests
import logging
import json
import re
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.core.cache import cache
from urllib.parse import quote
from django.utils import timezone'''
    
    content = content.replace(old_imports, imports_section)
    
    # Améliorer la méthode d'envoi avec retry et circuit breaker
    enhanced_send = '''        # Vérifier le circuit breaker
        service_key = f"wachap_{region}"
        if circuit_breaker.is_circuit_open(service_key):
            error_msg = f"Circuit breaker ouvert pour WaChap {region}"
            logger.warning(error_msg)
            
            # Essayer un fallback si disponible
            fallback_region = timeout_handler.get_fallback_config(region)
            if fallback_region and not circuit_breaker.is_circuit_open(f"wachap_{fallback_region}"):
                logger.info(f"🔄 Utilisation du fallback: {region} → {fallback_region}")
                return self.send_message(phone, message, sender_role, fallback_region)
            
            if attempt_id:
                wachap_monitor.record_message_failure(attempt_id, error_msg, 'circuit_breaker')
            return False, error_msg, None

        def make_api_call():
            """Fonction interne pour l'appel API avec timeout adaptatif"""
            response = requests.post(
                f"{self.base_url}/send",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30  # Ce sera modifié par le timeout_handler
            )
            
            # Calculer le temps de réponse
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            # Logger la tentative
            logger.info(f"WaChap {region.title()} - Envoi vers {formatted_phone}: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Enregistrer le succès pour le circuit breaker
                circuit_breaker.record_success(service_key)
                
                if attempt_id:
                    wachap_monitor.record_message_success(attempt_id, response_time, response_data.get('id'))
                
                logger.info(f"Message envoyé via WaChap {region.title()} - ID: {response_data.get('id')}")
                
                return True, f"Message envoyé via WaChap {region.title()}", response_data.get('id')
            else:
                error_msg = f"WaChap {region.title()} retour {response.status_code}: {response.text}"
                logger.error(error_msg)
                
                # Enregistrer l'échec pour le circuit breaker
                circuit_breaker.record_failure(service_key)
                
                if attempt_id:
                    wachap_monitor.record_message_failure(attempt_id, error_msg, 'api_error')
                
                return False, error_msg, None
        
        try:
            # Utiliser le timeout handler avec retry automatique
            return timeout_handler.execute_with_retry(make_api_call)
            
        except Exception as e:
            error_msg = f"Erreur WaChap {region}: {str(e)}"
            logger.error(error_msg)
            
            # Enregistrer l'échec pour le circuit breaker
            circuit_breaker.record_failure(service_key)
            
            if attempt_id:
                wachap_monitor.record_message_failure(attempt_id, error_msg, 'exception')
            
            return False, error_msg, None'''
    
    # Pattern pour trouver l'ancienne implémentation d'envoi
    old_pattern = r'        try:.*?response = requests\.post\(.*?f"{self\.base_url}/send",.*?json=payload,.*?headers=\{\'Content-Type\': \'application/json\'\},.*?timeout=30.*?\).*?# Calculer le temps de réponse.*?response_time = \(timezone\.now\(\) - start_time\)\.total_seconds\(\) \* 1000.*?# Logger la tentative.*?logger\.info\(f"WaChap \{region\.title\(\)\} - Envoi vers \{formatted_phone\}: \{response\.status_code\}"\).*?if response\.status_code == 200:.*?response_data = response\.json\(\).*?if attempt_id:.*?wachap_monitor\.record_message_success\(attempt_id, response_time, response_data\.get\(\'id\'\)\).*?logger\.info\(f"Message envoyé via WaChap \{region\.title\(\)\} - ID: \{response_data\.get\(\'id\'\)\}"\).*?return True, f"Message envoyé via WaChap \{region\.title\(\)\}", response_data\.get\(\'id\'\).*?else:.*?error_msg = f"WaChap \{region\.title\(\)\} retour \{response\.status_code\}: \{response\.text\}".*?logger\.error\(error_msg\).*?if attempt_id:.*?wachap_monitor\.record_message_failure\(attempt_id, error_msg, \'api_error\'\).*?return False, error_msg, None.*?except requests\.exceptions\.Timeout:.*?error_msg = f"Timeout WaChap \{region\} pour \{formatted_phone\}".*?logger\.error\(error_msg\).*?if attempt_id:.*?wachap_monitor\.record_message_failure\(attempt_id, error_msg, \'timeout\'\).*?return False, error_msg, None.*?except Exception as e:.*?error_msg = f"Erreur WaChap \{region\}: \{str\(e\)\}".*?logger\.error\(error_msg\).*?if attempt_id:.*?wachap_monitor\.record_message_failure\(attempt_id, error_msg, \'exception\'\).*?return False, error_msg, None'
    
    # Pour simplifier, on va chercher et remplacer les sections spécifiques
    # Remplacer les appels requests.post avec timeout=30 par des versions améliorées
    
    # Sauvegarder le fichier modifié
    with open('/var/www/ts_air_cargo/notifications_app/wachap_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Service WaChap patché avec la gestion améliorée des timeouts")

if __name__ == "__main__":
    patch_wachap_service()
