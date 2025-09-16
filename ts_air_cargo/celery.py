"""
Configuration Celery pour TS Air Cargo
"""

import os
from celery import Celery
import logging

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ts_air_cargo.settings')

app = Celery('ts_air_cargo')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

logger = logging.getLogger(__name__)

@app.task(bind=True)
def debug_task(self):
    logger.debug(f'Request: {self.request!r}')
