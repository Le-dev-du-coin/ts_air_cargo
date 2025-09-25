"""
Configuration Celery pour TS Air Cargo
Gestion des tâches asynchrones pour le traitement des colis
"""

import os
from celery import Celery
import logging

# Définir le module de settings Django par défaut pour 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')

# Créer l'instance Celery
app = Celery('ts_air_cargo')

# Utiliser string pour éviter la sérialisation lors de l'utilisation des workers
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscovery des tâches dans les apps Django
app.autodiscover_tasks()

logger = logging.getLogger(__name__)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Tâche de debug pour tester Celery
    """
    logger.info(f'Request: {self.request!r}')
    print(f'📝 Debug task executed: {self.request!r}')
    return 'Debug task completed'

# Configuration des workers
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True
app.conf.worker_disable_rate_limits = False

# Monitoring
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True

print("🚀 Celery configuré pour TS Air Cargo - Gestion asynchrone des colis")
